from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Float, DateTime
from sqlalchemy.orm import relationship
from core.database import Base
from datetime import datetime
import uuid

def generate_uuid():
    return str(uuid.uuid4())

class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=generate_uuid)
    username = Column(String, unique=True, index=True)
    password = Column(String)
    fullName = Column(String)
    role = Column(String)
    department = Column(String)
    avatar = Column(String)

class QueueTicket(Base):
    __tablename__ = "queue_tickets"
    id = Column(String, primary_key=True, default=generate_uuid)
    ticketNumber = Column(String, index=True)
    department = Column(String, index=True)
    position = Column(Integer)
    estimatedWaitTime = Column(Integer)
    timestamp = Column(String)
    status = Column(String, default="waiting")

class HistoryEntry(Base):
    __tablename__ = "history_entries"
    id = Column(String, primary_key=True) # Usually matches ticket ID
    ticketNumber = Column(String)
    department = Column(String)
    arrivalTime = Column(String)
    calledTime = Column(String)
    waitMinutes = Column(Integer)
    treatedBy = Column(String)
    status = Column(String, default="treated")

class Pharmacy(Base):
    __tablename__ = "pharmacies"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String)
    address = Column(String)
    latitude = Column(Float)
    longitude = Column(Float)
    
    stock = relationship("Medicine", back_populates="pharmacy", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="pharmacy", cascade="all, delete-orphan")

class Medicine(Base):
    __tablename__ = "medicines"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    pharmacy_id = Column(Integer, ForeignKey("pharmacies.id"))
    name = Column(String, index=True)
    inStock = Column(Boolean)
    quantity = Column(Integer)
    threshold = Column(Integer)
    category = Column(String)
    expirationDate = Column(String)
    
    pharmacy = relationship("Pharmacy", back_populates="stock")

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(String, primary_key=True, default=generate_uuid)
    pharmacy_id = Column(Integer, ForeignKey("pharmacies.id"))
    date = Column(String)
    medicine = Column(String)
    type = Column(String)
    quantity = Column(Integer)
    user = Column(String)
    
    pharmacy = relationship("Pharmacy", back_populates="transactions")

class Prescription(Base):
    __tablename__ = "prescriptions"
    id = Column(String, primary_key=True, default=generate_uuid)
    ticketId = Column(String, index=True)
    doctorName = Column(String)
    date = Column(String)
    notes = Column(String)
    status = Column(String, default="pending")
    deliveredAt = Column(String, nullable=True)
    deliveredBy = Column(String, nullable=True)
    
    medicines = relationship("PrescriptionMedicine", back_populates="prescription", cascade="all, delete-orphan")

class PrescriptionMedicine(Base):
    __tablename__ = "prescription_medicines"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    prescription_id = Column(String, ForeignKey("prescriptions.id"))
    name = Column(String)
    quantity = Column(Integer)
    dosage = Column(String)
    
    prescription = relationship("Prescription", back_populates="medicines")

class Availability(Base):
    __tablename__ = "availabilities"
    id = Column(String, primary_key=True, default=generate_uuid)
    doctorId = Column(String, index=True)
    date = Column(String, index=True)
    startTime = Column(String)
    endTime = Column(String)
    isBooked = Column(Boolean, default=False)

class Appointment(Base):
    __tablename__ = "appointments"
    id = Column(String, primary_key=True, default=generate_uuid)
    availabilityId = Column(String, ForeignKey("availabilities.id"))
    doctorId = Column(String)
    patientName = Column(String)
    patientPhone = Column(String)
    date = Column(String)
    startTime = Column(String)
    endTime = Column(String)
    reason = Column(String)
    status = Column(String, default="pending")
    createdAt = Column(String, default=lambda: datetime.now().isoformat())
