import os
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

import jwt
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text, create_engine, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://society:society@localhost:5432/society")
# Render provides a standard PostgreSQL URL; SQLAlchemy needs the installed psycopg driver explicitly.
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
SECRET_KEY = os.getenv("SECRET_KEY", "development-only-change-me")
ACCESS_TOKEN_MINUTES = int(os.getenv("ACCESS_TOKEN_MINUTES", "1440"))
pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False)

class Base(DeclarativeBase): pass
class Role(str, Enum): resident="resident"; admin="admin"
class ComplaintStatus(str, Enum): open="Open"; in_progress="In Progress"; resolved="Resolved"
class Priority(str, Enum): low="Low"; medium="Medium"; high="High"
class User(Base):
    __tablename__="users"
    id: Mapped[int] = mapped_column(primary_key=True); email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120)); password_hash: Mapped[str] = mapped_column(String(255)); role: Mapped[Role] = mapped_column(SAEnum(Role), default=Role.resident)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
class Complaint(Base):
    __tablename__="complaints"
    id: Mapped[int] = mapped_column(primary_key=True); category: Mapped[str] = mapped_column(String(80), index=True); title: Mapped[str] = mapped_column(String(180), index=True); description: Mapped[str] = mapped_column(Text)
    status: Mapped[ComplaintStatus] = mapped_column(SAEnum(ComplaintStatus), default=ComplaintStatus.open, index=True); priority: Mapped[Priority] = mapped_column(SAEnum(Priority), default=Priority.medium)
    photo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True); resident_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)); updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    resident: Mapped[User] = relationship(); history: Mapped[list["History"]] = relationship(back_populates="complaint", cascade="all, delete-orphan")
class History(Base):
    __tablename__="complaint_history"
    id: Mapped[int] = mapped_column(primary_key=True); complaint_id: Mapped[int] = mapped_column(ForeignKey("complaints.id"), index=True); actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    old_status: Mapped[Optional[ComplaintStatus]] = mapped_column(SAEnum(ComplaintStatus), nullable=True); new_status: Mapped[ComplaintStatus] = mapped_column(SAEnum(ComplaintStatus)); note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)); complaint: Mapped[Complaint] = relationship(back_populates="history"); actor: Mapped[User] = relationship()
class Notice(Base):
    __tablename__="notices"
    id: Mapped[int] = mapped_column(primary_key=True); title: Mapped[str] = mapped_column(String(180)); description: Mapped[str] = mapped_column(Text); important: Mapped[bool] = mapped_column(Boolean, default=False, index=True); author_id: Mapped[int] = mapped_column(ForeignKey("users.id")); created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
class Setting(Base):
    __tablename__="settings"
    key: Mapped[str] = mapped_column(String(80), primary_key=True); value: Mapped[str] = mapped_column(String(255))

class Register(BaseModel): name: str = Field(min_length=2,max_length=120); email: EmailStr; password: str = Field(min_length=8,max_length=100)
class Login(BaseModel): email: EmailStr; password: str
class ComplaintIn(BaseModel): category: str = Field(min_length=2,max_length=80); title: str = Field(min_length=3,max_length=180); description: str = Field(min_length=10,max_length=5000); photo_url: Optional[str]=None
class UpdateComplaint(BaseModel): status: Optional[ComplaintStatus]=None; priority: Optional[Priority]=None; note: Optional[str]=Field(default=None,max_length=2000)
class NoticeIn(BaseModel): title: str=Field(min_length=3,max_length=180); description: str=Field(min_length=3,max_length=5000); important: bool=False
class ThresholdIn(BaseModel): days: int=Field(ge=1,le=365)

def db():
    session=SessionLocal()
    try: yield session
    finally: session.close()
def serialize_user(u): return {"id":u.id,"name":u.name,"email":u.email,"role":u.role.value}
def token(u): return jwt.encode({"sub":str(u.id),"role":u.role.value,"exp":datetime.now(timezone.utc)+timedelta(minutes=ACCESS_TOKEN_MINUTES)},SECRET_KEY,algorithm="HS256")
security=HTTPBearer()
def current(c: HTTPAuthorizationCredentials=Depends(security), s:Session=Depends(db)):
    try: ident=int(jwt.decode(c.credentials,SECRET_KEY,algorithms=["HS256"])["sub"])
    except Exception: raise HTTPException(401,"Invalid or expired token")
    u=s.get(User,ident)
    if not u: raise HTTPException(401,"User unavailable")
    return u
def admin(u:User=Depends(current)):
    if u.role!=Role.admin: raise HTTPException(403,"Administrator access required")
    return u
def threshold(s):
    x=s.get(Setting,"overdue_days"); return int(x.value) if x else 3
def overdue(c,s):
    created=c.created_at if c.created_at.tzinfo else c.created_at.replace(tzinfo=timezone.utc)
    return c.status != ComplaintStatus.resolved and created < datetime.now(timezone.utc)-timedelta(days=threshold(s))
def serialize_complaint(c,s,detail=False):
    d={"id":c.id,"category":c.category,"title":c.title,"description":c.description,"status":c.status.value,"priority":c.priority.value,"photo_url":c.photo_url,"created_at":c.created_at,"updated_at":c.updated_at,"overdue":overdue(c,s),"resident":serialize_user(c.resident)}
    if detail: d["history"]=[{"id":h.id,"old_status":h.old_status.value if h.old_status else None,"new_status":h.new_status.value,"note":h.note,"created_at":h.created_at,"actor":serialize_user(h.actor)} for h in sorted(c.history,key=lambda h:h.created_at)]
    return d

app=FastAPI(title="Society Maintenance Tracker API",version="1.0.0")
app.add_middleware(CORSMiddleware,allow_origins=os.getenv("CORS_ORIGINS","http://localhost:3000").split(","),allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
Path(os.getenv("UPLOAD_DIR","uploads")).mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=os.getenv("UPLOAD_DIR","uploads")), name="uploads")
def send_email(to: str, subject: str, html: str):
    """Best-effort notifications; delivery is enabled only when Resend is configured."""
    key=os.getenv("RESEND_API_KEY")
    if not key: return
    import resend
    resend.api_key=key
    resend.Emails.send({"from":os.getenv("EMAIL_FROM","Society Tracker <onboarding@resend.dev>"),"to":[to],"subject":subject,"html":html})
@app.on_event("startup")
def init():
    if os.getenv("ENVIRONMENT")=="production" and SECRET_KEY=="development-only-change-me": raise RuntimeError("Set SECRET_KEY in production")
    Base.metadata.create_all(engine)
    with SessionLocal() as s:
        if not s.get(Setting,"overdue_days"): s.add(Setting(key="overdue_days",value="3"))
        if os.getenv("SEED_DEMO","false").lower()=="true" and not s.scalar(select(User).where(User.email=="admin@demo.example.com")):
            s.add_all([User(name="Society Admin",email="admin@demo.example.com",password_hash=pwd.hash("Admin123!"),role=Role.admin),User(name="Demo Resident",email="resident@demo.example.com",password_hash=pwd.hash("Resident123!"),role=Role.resident)])
        s.commit()
@app.get("/health")
def health(): return {"ok":True}
@app.post("/auth/register",status_code=201)
def register(x:Register,s:Session=Depends(db)):
    if s.scalar(select(User).where(User.email==x.email)): raise HTTPException(409,"Email is already registered")
    u=User(name=x.name,email=x.email,password_hash=pwd.hash(x.password)); s.add(u); s.commit(); s.refresh(u); return {"access_token":token(u),"user":serialize_user(u)}
@app.post("/auth/login")
def login(x:Login,s:Session=Depends(db)):
    u=s.scalar(select(User).where(User.email==x.email))
    if not u or not pwd.verify(x.password,u.password_hash): raise HTTPException(401,"Incorrect email or password")
    return {"access_token":token(u),"user":serialize_user(u)}
@app.get("/auth/me")
def me(u:User=Depends(current)): return serialize_user(u)
@app.get("/complaints")
def complaints(q:Optional[str]=None,status_:Optional[ComplaintStatus]=None,category:Optional[str]=None,from_date:Optional[datetime]=None,to_date:Optional[datetime]=None,s:Session=Depends(db),u:User=Depends(current)):
    st=select(Complaint).order_by(Complaint.created_at.desc()); st=st.where(Complaint.resident_id==u.id) if u.role==Role.resident else st
    if q: st=st.where(Complaint.title.ilike(f"%{q}%"))
    if status_: st=st.where(Complaint.status==status_)
    if category: st=st.where(Complaint.category==category)
    if from_date: st=st.where(Complaint.created_at>=from_date)
    if to_date: st=st.where(Complaint.created_at<=to_date)
    return [serialize_complaint(c,s) for c in s.scalars(st).unique()]
@app.post("/complaints",status_code=201)
def create_complaint(x:ComplaintIn,s:Session=Depends(db),u:User=Depends(current)):
    c=Complaint(**x.model_dump(),resident_id=u.id); s.add(c); s.flush(); s.add(History(complaint_id=c.id,actor_id=u.id,old_status=None,new_status=ComplaintStatus.open,note="Complaint created")); s.commit(); s.refresh(c); return serialize_complaint(c,s,True)
@app.get("/complaints/{id}")
def complaint(id:int,s:Session=Depends(db),u:User=Depends(current)):
    c=s.get(Complaint,id)
    if not c or (u.role==Role.resident and c.resident_id!=u.id): raise HTTPException(404,"Complaint not found")
    return serialize_complaint(c,s,True)
@app.patch("/complaints/{id}")
def update_complaint(id:int,x:UpdateComplaint,s:Session=Depends(db),u:User=Depends(admin)):
    c=s.get(Complaint,id)
    if not c: raise HTTPException(404,"Complaint not found")
    if x.priority: c.priority=x.priority
    if x.status and x.status!=c.status:
        old=c.status; s.add(History(complaint_id=id,actor_id=u.id,old_status=old,new_status=x.status,note=x.note)); c.status=x.status
        s.commit(); s.refresh(c)
        try: send_email(c.resident.email, f"Complaint update: {c.title}", f"<p>Your complaint <b>{c.title}</b> changed from {old.value} to <b>{c.status.value}</b>.</p><p>{x.note or ''}</p>")
        except Exception: pass
        return serialize_complaint(c,s,True)
    s.commit(); s.refresh(c); return serialize_complaint(c,s,True)
@app.post("/uploads")
async def upload(file:UploadFile=File(...),u:User=Depends(current)):
    if file.content_type not in {"image/jpeg","image/png","image/webp"}: raise HTTPException(415,"Use JPG, PNG, or WEBP")
    data=await file.read()
    if len(data)>5_000_000: raise HTTPException(413,"Image must be 5 MB or smaller")
    folder=Path(os.getenv("UPLOAD_DIR","uploads")); folder.mkdir(parents=True,exist_ok=True); name=f"{datetime.now().timestamp()}-{file.filename}"; (folder/name).write_bytes(data); return {"url":f"/{folder}/{name}"}
@app.get("/settings/overdue")
def get_threshold(s:Session=Depends(db),u:User=Depends(admin)): return {"days":threshold(s)}
@app.put("/settings/overdue")
def set_threshold(x:ThresholdIn,s:Session=Depends(db),u:User=Depends(admin)): s.merge(Setting(key="overdue_days",value=str(x.days))); s.commit(); return {"days":x.days}
@app.get("/notices")
def notices(s:Session=Depends(db),u:User=Depends(current)): return [{"id":n.id,"title":n.title,"description":n.description,"important":n.important,"created_at":n.created_at} for n in s.scalars(select(Notice).order_by(Notice.important.desc(),Notice.created_at.desc()))]
@app.post("/notices",status_code=201)
def create_notice(x:NoticeIn,s:Session=Depends(db),u:User=Depends(admin)):
    n=Notice(**x.model_dump(),author_id=u.id);s.add(n);s.commit();s.refresh(n)
    if n.important:
        for email in s.scalars(select(User.email).where(User.role==Role.resident)):
            try: send_email(email,f"Important notice: {n.title}",f"<h2>{n.title}</h2><p>{n.description}</p>")
            except Exception: pass
    return {"id":n.id,"title":n.title,"description":n.description,"important":n.important,"created_at":n.created_at}
@app.put("/notices/{id}")
def update_notice(id:int,x:NoticeIn,s:Session=Depends(db),u:User=Depends(admin)):
    n=s.get(Notice,id)
    if not n: raise HTTPException(404,"Notice not found")
    n.title,n.description,n.important=x.title,x.description,x.important;s.commit();s.refresh(n)
    if n.important:
        for email in s.scalars(select(User.email).where(User.role==Role.resident)):
            try: send_email(email,f"Important notice: {n.title}",f"<h2>{n.title}</h2><p>{n.description}</p>")
            except Exception: pass
    return {"id":n.id,"title":n.title,"description":n.description,"important":n.important,"created_at":n.created_at}
@app.delete("/notices/{id}",status_code=204)
def delete_notice(id:int,s:Session=Depends(db),u:User=Depends(admin)):
    n=s.get(Notice,id)
    if not n: raise HTTPException(404,"Notice not found")
    s.delete(n);s.commit()
@app.get("/dashboard")
def dashboard(s:Session=Depends(db),u:User=Depends(current)):
    cs=list(s.scalars(select(Complaint).where(Complaint.resident_id==u.id) if u.role==Role.resident else select(Complaint)).unique())
    return {"total":len(cs),"open":sum(c.status==ComplaintStatus.open for c in cs),"in_progress":sum(c.status==ComplaintStatus.in_progress for c in cs),"resolved":sum(c.status==ComplaintStatus.resolved for c in cs),"overdue":sum(overdue(c,s) for c in cs),"by_category":{k:sum(c.category==k for c in cs) for k in set(c.category for c in cs)}}
