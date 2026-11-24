from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    role = db.Column(db.String(20)) # donor, beneficiary, admin

class Donation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    donor_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    item = db.Column(db.String(50))
    quantity = db.Column(db.Integer)
    image_file = db.Column(db.String(100), default='default.jpg')  # New: Image Upload
    address = db.Column(db.String(200)) # New: Pickup Address
    phone = db.Column(db.String(20))    # New: Contact Phone
    status = db.Column(db.String(20), default="Pending Pickup") # Pending Pickup, Collected
    date_added = db.Column(db.DateTime, default=db.func.current_timestamp())
    
    # Relationship for pickup delivery
    delivery = db.relationship('Delivery', backref='donation', uselist=False)

class Request(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    beneficiary_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    item = db.Column(db.String(50))
    quantity = db.Column(db.Integer)
    address = db.Column(db.String(200)) # New: Delivery Address
    phone = db.Column(db.String(20))    # New: Contact Phone
    status = db.Column(db.String(20), default="Pending") # Pending, Approved, Rejected

    # Relationship for dropoff delivery
    delivery = db.relationship('Delivery', backref='request', uselist=False)

class Inventory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item = db.Column(db.String(50))
    quantity = db.Column(db.Integer)

class Delivery(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(20)) # "Pickup" (from donor) or "Dropoff" (to beneficiary)
    related_id = db.Column(db.Integer) # Stores Donation ID or Request ID depending on type
    
    # We use foreign keys to link optionally
    donation_id = db.Column(db.Integer, db.ForeignKey('donation.id'), nullable=True)
    request_id = db.Column(db.Integer, db.ForeignKey('request.id'), nullable=True)
    
    vehicle = db.Column(db.String(50))
    driver = db.Column(db.String(50))
    status = db.Column(db.String(20), default="Assigned") # Assigned, Completed