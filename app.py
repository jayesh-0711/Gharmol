from flask import Flask, request, jsonify, render_template, redirect, url_for, flash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_bcrypt import Bcrypt
import pickle
import pandas as pd
from geopy.geocoders import Nominatim
from models import db, User, Prediction, Property
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 # 16 MB max

db.init_app(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Load model
model = pickle.load(open("model.pkl", "rb"))
geolocator = Nominatim(user_agent="house_price_app")

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.before_request
def create_tables():
    app.before_request_funcs[None].remove(create_tables)
    db.create_all()

@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        action = request.form.get("action")
        
        if action == "signup":
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                flash("Email already exists. Please log in.", "danger")
            else:
                hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
                new_user = User(email=email, password=hashed_password)
                db.session.add(new_user)
                db.session.commit()
                flash("Account created! You can now log in.", "success")
                return redirect(url_for('login'))
                
        elif action == "login":
            user = User.query.filter_by(email=email).first()
            if user and bcrypt.check_password_hash(user.password, password):
                login_user(user)
                return redirect(url_for('dashboard'))
            else:
                flash("Login Unsuccessful. Please check email and password", "danger")
                
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route("/dashboard")
@login_required
def dashboard():
    total_predictions = Prediction.query.filter_by(user_id=current_user.id).count()
    predictions = Prediction.query.filter_by(user_id=current_user.id).order_by(Prediction.created_at.desc()).all()
    avg_price = sum(p.predicted_price for p in predictions) / total_predictions if total_predictions > 0 else 0
    my_properties = Property.query.filter_by(user_id=current_user.id).order_by(Property.created_at.desc()).all()
    
    profile_steps_completed = sum(bool(x) for x in [current_user.name, current_user.address, current_user.contact_no])
    
    return render_template("dashboard.html", 
                           total_predictions=total_predictions, 
                           avg_price=round(avg_price, 2),
                           predictions=predictions,
                           properties=my_properties,
                           profile_steps_completed=profile_steps_completed)

@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        current_user.name = request.form.get("name")
        current_user.address = request.form.get("address")
        current_user.contact_no = request.form.get("contact_no")
        db.session.commit()
        flash("Profile updated successfully!", "success")
        return redirect(url_for('profile'))
        
    return render_template("profile.html")

@app.route("/predict", methods=["GET", "POST"])
@login_required
def predict():
    if request.method == "POST":
        lat = float(request.form.get("lat"))
        lng = float(request.form.get("lng"))
        location_name = request.form.get("location", "Unknown Location")
        total_sqft = max(1000.0, float(request.form.get("total_sqft")))
        
        bhk_val = request.form.get("bhk", "")
        bath_val = request.form.get("bath", "")
        
        bhk = max(1, int(bhk_val)) if bhk_val != "" else 1
        bath = max(1, int(bath_val)) if bath_val != "" else 1

        if not (12.7 <= lat <= 13.2 and 77.4 <= lng <= 77.8):
            flash("Location is outside Bangalore! Please select a location within Bangalore.", "danger")
            return redirect(url_for("predict",
                                    lat=lat,
                                    lng=lng,
                                    location=location_name,
                                    total_sqft=total_sqft,
                                    bhk=bhk_val,
                                    bath=bath_val))

        center_lat, center_lng = 12.9716, 77.5946
        distance = ((lat - center_lat)**2 + (lng - center_lng)**2)**0.5
        location_code = int(distance * 50000)

        df = pd.DataFrame([[location_code, total_sqft, bhk, bath]],
                          columns=['location','total_sqft','BHK','bath'])

        prediction_val = model.predict(df)[0]
        prediction_val = max(0, prediction_val)
        
        new_pred = Prediction(user_id=current_user.id, location=location_name, sqft=total_sqft, bhk=bhk, bath=bath, predicted_price=round(prediction_val, 2))
        db.session.add(new_pred)
        db.session.commit()

        flash(f"Predicted Price for {location_name}: ₹{round(prediction_val, 2)} Lakhs", "success")
        return redirect(url_for("predict",
                                lat=lat,
                                lng=lng,
                                location=location_name,
                                total_sqft=total_sqft,
                                bhk=bhk_val,
                                bath=bath_val))
        
    result = {
        'lat': request.args.get('lat', ''),
        'lng': request.args.get('lng', ''),
        'location': request.args.get('location', ''),
        'total_sqft': request.args.get('total_sqft', ''),
        'bhk': request.args.get('bhk', ''),
        'bath': request.args.get('bath', '')
    }
    has_result = any(result.values())
    return render_template("predict.html", result=result if has_result else None)

@app.route("/heatmap")
@login_required
def heatmap():
    return render_template("heatmap.html")

@app.route("/compare", methods=["GET", "POST"])
@login_required
def compare():
    if request.method == "POST":
        # Property A
        lat_a = float(request.form.get("lat_a"))
        lng_a = float(request.form.get("lng_a"))
        sqft_a = max(100.0, float(request.form.get("sqft_a")))
        bhk_a = max(1, int(request.form.get("bhk_a", 1)))
        bath_a = max(1, int(request.form.get("bath_a", 1)))
        
        # Property B
        lat_b = float(request.form.get("lat_b"))
        lng_b = float(request.form.get("lng_b"))
        sqft_b = max(100.0, float(request.form.get("sqft_b")))
        bhk_b = max(1, int(request.form.get("bhk_b", 1)))
        bath_b = max(1, int(request.form.get("bath_b", 1)))

        center_lat, center_lng = 12.9716, 77.5946
        
        dist_a = ((lat_a - center_lat)**2 + (lng_a - center_lng)**2)**0.5
        loc_code_a = int(dist_a * 50000)
        df_a = pd.DataFrame([[loc_code_a, sqft_a, bhk_a, bath_a]], columns=['location','total_sqft','BHK','bath'])
        price_a = max(0, model.predict(df_a)[0])
        
        dist_b = ((lat_b - center_lat)**2 + (lng_b - center_lng)**2)**0.5
        loc_code_b = int(dist_b * 50000)
        df_b = pd.DataFrame([[loc_code_b, sqft_b, bhk_b, bath_b]], columns=['location','total_sqft','BHK','bath'])
        price_b = max(0, model.predict(df_b)[0])

        diff = abs(price_a - price_b)
        percent_diff = (diff / max(price_a, price_b)) * 100 if max(price_a, price_b) > 0 else 0

        result = {
            "price_a": round(price_a, 2),
            "price_b": round(price_b, 2),
            "difference": round(diff, 2),
            "percent_diff": round(percent_diff, 1)
        }
        return render_template("compare.html", result=result)

    return render_template("compare.html")

@app.route("/insights")
@login_required
def insights():
    return render_template("insights.html")

@app.route("/add-property", methods=["GET", "POST"])
@login_required
def add_property():
    if request.method == "POST":
        property_type = request.form.get("property_type")
        listing_type = request.form.get("listing_type", "Sell")
        title = request.form.get("title")
        description = request.form.get("description")
        price = float(request.form.get("price"))
        location_name = request.form.get("location_name")
        lat = float(request.form.get("lat"))
        lng = float(request.form.get("lng"))
        
        # Handling the image
        file = request.files.get("image")
        image_filename = "default_property.jpg"
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            image_filename = filename
            
        new_property = Property(
            user_id=current_user.id,
            property_type=property_type,
            listing_type=listing_type,
            title=title,
            description=description,
            price=price,
            location_name=location_name,
            lat=lat,
            lng=lng,
            image_file=image_filename
        )
        
        new_property.sqft = float(request.form.get("sqft", 0))
        
        if property_type in ["House", "Villa", "Apartment"]:
            new_property.bhk = int(request.form.get("bhk", 0))
            new_property.bath = int(request.form.get("bath", 0))
            new_property.floors = int(request.form.get("floors", 0))
        elif property_type in ["Land", "Agricultural Land"]:
            new_property.is_agricultural = (property_type == "Agricultural Land")
            
        db.session.add(new_property)
        db.session.commit()
        flash("Property listed successfully!", "success")
        return redirect(url_for('dashboard'))
        
    return render_template("add_property.html")

@app.route("/edit-property/<int:prop_id>", methods=["GET", "POST"])
@login_required
def edit_property(prop_id):
    prop = Property.query.get_or_404(prop_id)
    if prop.user_id != current_user.id:
        flash("Unauthorized to edit this property.", "danger")
        return redirect(url_for('dashboard'))
        
    if request.method == "POST":
        prop.title = request.form.get("title")
        prop.description = request.form.get("description")
        prop.price = float(request.form.get("price"))
        prop.location_name = request.form.get("location_name")
        prop.lat = float(request.form.get("lat"))
        prop.lng = float(request.form.get("lng"))
        
        if prop.property_type in ["House", "Villa", "Apartment"]:
            prop.sqft = float(request.form.get("sqft", 0))
            prop.bhk = int(request.form.get("bhk", 0))
            prop.bath = int(request.form.get("bath", 0))
            prop.floors = int(request.form.get("floors", 0))
        elif prop.property_type in ["Land", "Agricultural Land"]:
            prop.sqft = float(request.form.get("sqft", 0))
            
        file = request.files.get("image")
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            prop.image_file = filename
            
        db.session.commit()
        flash("Property updated successfully!", "success")
        return redirect(url_for('property_detail', prop_id=prop.id))
        
    return render_template("edit_property.html", prop=prop)

@app.route("/delete-property/<int:prop_id>", methods=["POST"])
@login_required
def delete_property(prop_id):
    prop = Property.query.get_or_404(prop_id)
    if prop.user_id != current_user.id:
        flash("Unauthorized to delete this property.", "danger")
        return redirect(url_for('dashboard'))
        
    db.session.delete(prop)
    db.session.commit()
    flash("Property removed successfully.", "success")
    return redirect(url_for('dashboard'))

@app.route("/properties")
@login_required
def properties():
    property_type = request.args.get("type", "All")
    min_price = request.args.get("min_price", type=float)
    max_price = request.args.get("max_price", type=float)
    search_q = request.args.get("location", "")
    
    # Do not show properties owned by current user in the market
    query = Property.query.filter(Property.user_id != current_user.id)
    
    if property_type != "All":
        query = query.filter(Property.property_type == property_type)
        
    if min_price is not None:
        query = query.filter(Property.price >= min_price)
    if max_price is not None:
        query = query.filter(Property.price <= max_price)
    if search_q:
        query = query.filter(
            db.or_(
                Property.location_name.ilike(f"%{search_q}%"),
                Property.property_type.ilike(f"%{search_q}%"),
                Property.title.ilike(f"%{search_q}%")
            )
        )
        
    all_properties = query.order_by(Property.created_at.desc()).all()
    
    return render_template("properties.html", properties=all_properties, filters=request.args)

@app.route("/property/<int:prop_id>")
@login_required
def property_detail(prop_id):
    prop = Property.query.get_or_404(prop_id)
    
    ai_valuation = None
    ai_status = ""
    # Run AI prediction for all property types
    sqft_val = max(100.0, float(prop.sqft or 1000.0))
    bhk_val = max(1, int(prop.bhk or 1))
    bath_val = max(1, int(prop.bath or 1))
    
    center_lat, center_lng = 12.9716, 77.5946
    distance = ((prop.lat - center_lat)**2 + (prop.lng - center_lng)**2)**0.5
    location_code = int(distance * 50000)

    df = pd.DataFrame([[location_code, sqft_val, bhk_val, bath_val]],
                      columns=['location','total_sqft','BHK','bath'])
    predicted_val = model.predict(df)[0]
    predicted_val = max(0, predicted_val) # comes in Lakhs
    ai_valuation = round(predicted_val, 2)
    
    # Simple valuation logic
    asking_price_lakhs = prop.price / 100000  # assuming asking price is in exact rupees
    
    ai_difference_rupees = abs((ai_valuation * 100000) - prop.price)
    
    if asking_price_lakhs < ai_valuation * 0.9:
        ai_status = "Great Deal! 💥"
    elif asking_price_lakhs > ai_valuation * 1.1:
        ai_status = "Overpriced 📈"
    else:
        ai_status = "Fairly Priced 🤝"

    return render_template("property_detail.html", prop=prop, ai_valuation=ai_valuation, ai_status=ai_status, ai_difference_rupees=ai_difference_rupees)

if __name__ == "__main__":
    app.run(debug=True)