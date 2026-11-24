import os
import subprocess
import webbrowser
from threading import Timer
from flask import Flask, render_template, request, redirect, session, url_for, flash
from werkzeug.utils import secure_filename
from models import db, User, Donation, Request, Inventory, Delivery

# --- APP CONFIGURATION ---
app = Flask(__name__)
app.secret_key = "super_secret_key"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cloth.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Image Upload Config
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

db.init_app(app)

with app.app_context():
    db.create_all()
    # Create Admin if not exists
    if not User.query.filter_by(email='admin@gmail.com').first():
        admin = User(name='Super Admin', email='admin@gmail.com', password='admin', role='admin')
        db.session.add(admin)
        db.session.commit()

# --- AUTH ROUTES ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email, password=password).first()
        if user:
            session['user_id'] = user.id
            session['name'] = user.name
            session['role'] = user.role
            return redirect(f'/{user.role}_dashboard')
        flash('Invalid Credentials', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']
        if User.query.filter_by(email=email).first():
            flash('Email exists', 'warning')
            return redirect('/register')
        user = User(name=name, email=email, password=password, role=role)
        db.session.add(user)
        db.session.commit()
        return redirect('/login')
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# --- DONOR ROUTES ---
@app.route('/donor_dashboard', methods=['GET', 'POST'])
def donor_dashboard():
    if session.get('role') != 'donor': return redirect('/login')
    
    if request.method == 'POST':
        item = request.form['item']
        qty = int(request.form['quantity'])
        address = request.form['address']
        phone = request.form['phone']
        
        file = request.files['image']
        filename = 'default.jpg'
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        donation = Donation(donor_id=session['user_id'], item=item, quantity=qty, 
                            image_file=filename, address=address, phone=phone)
        db.session.add(donation)
        db.session.commit()
        flash('Donation listed! Wait for driver assignment.', 'success')
        
    donations = Donation.query.filter_by(donor_id=session['user_id']).order_by(Donation.id.desc()).all()
    return render_template('donor_dashboard.html', donations=donations)

# --- ROUTE: DONOR CONFIRMS PICKUP ---
@app.route('/confirm_pickup/<int:id>')
def confirm_pickup(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    donation = Donation.query.get(id)
    if donation:
        donation.status = 'Collected'
        db.session.commit()
        flash('Pickup confirmed! Thank you for your donation.', 'success')
    
    return redirect(url_for('donor_dashboard'))

# --- BENEFICIARY ROUTES ---
@app.route('/beneficiary_dashboard', methods=['GET', 'POST'])
def beneficiary_dashboard():
    if session.get('role') != 'beneficiary': return redirect('/login')
    
    if request.method == 'POST':
        item = request.form['item']
        qty = request.form['quantity']
        address = request.form['address']
        phone = request.form['phone']
        
        req = Request(beneficiary_id=session['user_id'], item=item, quantity=qty, address=address, phone=phone)
        db.session.add(req)
        db.session.commit()
        flash('Request submitted!', 'info')
        
    my_requests = Request.query.filter_by(beneficiary_id=session['user_id']).order_by(Request.id.desc()).all()
    return render_template('beneficiary_dashboard.html', requests=my_requests)

# --- USER CONFIRM RECEIPT ---
@app.route('/confirm_receipt/<int:id>')
def confirm_receipt(id):
    if session.get('role') != 'beneficiary': return redirect('/login')
    req = Request.query.get(id)
    if req and req.beneficiary_id == session['user_id']:
        req.status = "Received by User"
        db.session.commit()
        flash('Thanks for confirming delivery!', 'success')
    return redirect('/beneficiary_dashboard')

# --- ADMIN DASHBOARD ---
@app.route('/admin_dashboard')
def admin_dashboard():
    if session.get('role') != 'admin': return redirect('/login')
    
    requests = Request.query.order_by(Request.id.desc()).all()
    donations = Donation.query.order_by(Donation.id.desc()).all()
    inventory = Inventory.query.all()
    deliveries = Delivery.query.all()
    
    inv_labels = [i.item for i in inventory]
    inv_data = [i.quantity for i in inventory]
    
    return render_template('admin_dashboard.html', 
                           requests=requests, 
                           donations=donations, 
                           inventory=inventory, 
                           deliveries=deliveries,
                           inv_labels=inv_labels,
                           inv_data=inv_data)

# --- ADMIN ACTIONS ---
@app.route('/approve_request/<int:id>')
def approve_request(id):
    req = Request.query.get(id)
    inv = Inventory.query.filter_by(item=req.item).first()
    if inv and inv.quantity >= req.quantity:
        inv.quantity -= req.quantity
        req.status = "Approved"
        db.session.commit()
        flash('Request Approved. Assign a driver next.', 'success')
    else:
        flash('Not enough inventory!', 'danger')
    return redirect('/admin_dashboard')

@app.route('/reject_request/<int:id>')
def reject_request(id):
    req = Request.query.get(id)
    req.status = "Rejected"
    db.session.commit()
    return redirect('/admin_dashboard')

@app.route('/delete_request/<int:id>')
def delete_request(id):
    req = Request.query.get(id)
    db.session.delete(req)
    db.session.commit()
    return redirect('/admin_dashboard')

@app.route('/assign_driver', methods=['POST'])
def assign_driver():
    task_type = request.form['type']
    task_id = request.form['id']
    vehicle = request.form['vehicle']
    driver = request.form['driver']
    
    if task_type == 'Pickup':
        donation = Donation.query.get(task_id)
        donation.status = "Driver Assigned"
        new_delivery = Delivery(type="Pickup", donation_id=donation.id, vehicle=vehicle, driver=driver)
        flash(f'Driver {driver} dispatched to collect {donation.item}.', 'info')
        
    elif task_type == 'Dropoff':
        new_delivery = Delivery(type="Dropoff", request_id=task_id, vehicle=vehicle, driver=driver)
        flash(f'Driver {driver} dispatched to deliver.', 'info')
    
    db.session.add(new_delivery)
    db.session.commit()
    return redirect('/admin_dashboard')

# --- CONFIRM ARRIVAL (Admin) ---
@app.route('/confirm_arrival/<int:id>')
def confirm_arrival(id):
    donation = Donation.query.get(id)
    if donation.status == 'Driver Assigned' or donation.status == 'Collected':
        inv = Inventory.query.filter_by(item=donation.item).first()
        if inv: inv.quantity += donation.quantity
        else: db.session.add(Inventory(item=donation.item, quantity=donation.quantity))
        
        donation.status = "In Stock"
        db.session.commit()
        flash(f'Item arrived at warehouse! Inventory updated.', 'success')
    return redirect('/admin_dashboard')

# --- DESKTOP APP LAUNCHER ---
def launch_app():
    """
    Tries to open in 'App Mode' (No tabs, standalone window) via Edge.
    If Edge is missing, it falls back to the default browser.
    """
    url = "http://127.0.0.1:5000"
    try:
        # Command to open Edge in App Mode
        subprocess.Popen(f'start msedge --app={url}', shell=True)
    except:
        # Fallback to standard browser tab
        webbrowser.open_new(url)

if __name__ == "__main__":
    # Wait 1.5 seconds for server to start, then launch window
    Timer(1.5, launch_app).start()
    
    # Run Server
    app.run(debug=True, use_reloader=False)