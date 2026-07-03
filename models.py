from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    name = db.Column(db.String(150), nullable=True)
    address = db.Column(db.Text, nullable=True)
    contact_no = db.Column(db.String(50), nullable=True)
    profile_prompt_dismissed = db.Column(db.Boolean, default=False)
    predictions = db.relationship('Prediction', backref='user', lazy=True)
    properties = db.relationship('Property', backref='owner', lazy=True)

class Prediction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    location = db.Column(db.String(150), nullable=False)
    sqft = db.Column(db.Float, nullable=False)
    bhk = db.Column(db.Integer, nullable=False)
    bath = db.Column(db.Integer, nullable=False)
    predicted_price = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Property(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    property_type = db.Column(db.String(50), nullable=False) # 'House' or 'Land'
    listing_type = db.Column(db.String(50), nullable=True, default='Sell')
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Float, nullable=False)
    location_name = db.Column(db.String(150), nullable=False)
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)
    image_file = db.Column(db.String(150), nullable=True, default='default_property.jpg')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # House specific
    sqft = db.Column(db.Float, nullable=True)
    bhk = db.Column(db.Integer, nullable=True)
    bath = db.Column(db.Integer, nullable=True)
    floors = db.Column(db.Integer, nullable=True)
    
    # Land specific
    is_agricultural = db.Column(db.Boolean, nullable=True, default=False)
