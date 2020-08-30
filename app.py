from flask import Flask, flash, render_template, request, redirect, url_for
import os
import pymongo
import flask_login
from dotenv import load_dotenv
from bson.objectid import ObjectId
import datetime
from passlib.hash import pbkdf2_sha256
import math

load_dotenv()

app = Flask(__name__)

app.secret_key = os.environ.get('SECRET_KEY')

MONGO_URI = os.environ.get('MONGO_URI')
DB_NAME = "vroom"

client = pymongo.MongoClient(MONGO_URI)
db = client[DB_NAME]

# Login


class User(flask_login.UserMixin):
    pass


# init flask-login
login_manager = flask_login.LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


@login_manager.user_loader
def user_loader(email):
    user = db.users.find_one({
        'email': email
    })

    # if the email exists
    if user:
        # create a User object that represents the user session
        user_object = User()
        # store the email of the user in the session as `id`
        user_object.id = user["email"]
        # store the unique id of the user in the session as `account_id`
        user_object.account_id = user["_id"]
        # return the User object
        user_object.username = user["username"]
        user_object.phone = user["phone"]
        return user_object
    else:
        # if the email does not exist in the database, report an error
        return None


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/register')
def register():
    return render_template('register.template.html')


@app.route('/register', methods=["POST"])
def process_register():

    # extract out the email and password
    email = request.form.get('email')
    password = request.form.get('password')
    username = request.form.get('username')
    phone = request.form.get('phone')

    # TODO: Vadliate if the email and password are proper
    users = db.users.find_one({
        'email': email
    })
    if users:
        flash("Email already exists", "danger")
        previous_values = request.form.to_dict()
        return render_template('register.template.html', previous_values=previous_values)
    else:
        # Create the new user
        db.users.insert_one({
            'email': email,
            'password': pbkdf2_sha256.hash(password),
            'username': username,
            'phone': phone
        })

        flash("Sign up successful", "success")

        # Redirect to the login page
        return redirect(url_for('login'))


@app.route('/login')
def login():
    return render_template('login.template.html')


@app.route('/login', methods=["POST"])
def process_login():
    # retrieve the email and the password from the form
    email = request.form.get('email')
    password = request.form.get('password')

    # check if the user's email exists in the database
    user = db.users.find_one({
        'email': email
    })

    # if the user exists, chec if the password matches
    if user and pbkdf2_sha256.verify(password, user["password"]):
        # if the password matches, authorize the user
        user_object = User()
        # save the email of the user in the session as the property `id`
        user_object.id = user["email"]
        # save the unique id of the user in the session as the property
        # `account_id`
        user_object.account_id = user["_id"]

        user_object.username = user["username"]
        # create the user session
        flask_login.login_user(user_object)

        # redirect to a page and says login is successful
        flash("Login successful", "success")
        return redirect(url_for('show_all_listings'))

    # if the login failed, return back to the login page
    else:
        flash("Wrong email or password", "danger")
        return redirect(url_for('login'))


@app.route('/logout')
def logout():
    flask_login.logout_user()
    flash('Logged out', 'success')
    return redirect(url_for('login'))

# Main page route


@app.route("/")
def show_index():
    return render_template("index.html")


@app.route("/all_listings")
def show_all_listings():
    listings = db.listings.find()
    return render_template("all_listings.template.html", listings=listings)

# Create a listing page


@app.route("/create")
@flask_login.login_required
def show_create():
    car_brand = db.brands.find()
    return render_template("create_listing.template.html", car_brand=car_brand)


@app.route("/create", methods=["POST"])
@flask_login.login_required
def process_create():

    # retrieve information from the create form
    brand_id = request.form.get("car_brand")
    car_model = request.form.get("car_model")
    car_type = request.form.get("car_type")
    car_hp = request.form.get("car_hp")
    car_condition = request.form.get("car_condition")
    car_year = request.form.get("car_year")
    car_price = request.form.get("car_price")
    car_mileage = request.form.get("car_mileage")

    # check for error messages

    # accumulator

    errors = {}

    # check if name of car brand has at least 2 letters

    if len(car_model) < 2:
        errors.update(
            model_too_short="Please key in at least 2 letters for car model.")

    if len(errors) > 0:
        car_brand = db.brands.find()
        flash("Unable to create listing", "danger")
        previous_values = request.form.to_dict()
        previous_values['car_brand'] = ObjectId(previous_values['car_brand'])
        return render_template("create_listing.template.html", errors=errors, previous_values=previous_values, car_brand=car_brand)

    # fetch the info of the brand by its ID

    car_brand = db.brands.find_one({
        '_id': ObjectId(brand_id)
    })

    # fetch the info of the user by its ID

    # create the query
    new_listing = {
        'seller_id': flask_login.current_user.account_id,
        'seller_name': flask_login.current_user.username,
        # 'seller_contact' : flask_login.current_user.phone,
        'car': {
            '_id': ObjectId(brand_id),
            'car_brand': car_brand["brand"],
            'car_model': car_model,
            'car_type': car_type,
            'car_hp': car_hp,
            'car_condition': car_condition,
            'car_year': car_year,
            'car_price': car_price,
            'car_mileage': car_mileage
        }
    }

    # execute the query

    inserted_listing = db.listings.insert_one(new_listing)

    flash("New listing has been created!", "success")

    return redirect(url_for('show_created', inserted_listing_id=inserted_listing.inserted_id))

# Show Created listing


@app.route("/created/<inserted_listing_id>")
def show_created(inserted_listing_id):
    listing = db.listings.find({
        '_id': ObjectId(inserted_listing_id)
    })
    car_brand = db.brands.find()
    return render_template("created_listing.template.html", listing=listing)


@app.route("/my_listings/<seller_id>")
@flask_login.login_required
def show_my_listings(seller_id):
    seller_id = flask_login.current_user.account_id
    listings = db.listings.find({
        'seller_id': ObjectId(seller_id)
    })
    if ObjectId(seller_id) == flask_login.current_user.account_id:
        return render_template("my_listings.template.html", listings=listings, seller_id=ObjectId(seller_id))
    else:
        return redirect(url_for("show_all_listings"))


@app.route("/seller_listings/<seller_id>")
def show_seller_listings(seller_id):
    listings = db.listings.find({
        'seller_id': ObjectId(seller_id)
    })
    seller_listing = db.listings.find_one({
        '_id' : ObjectId()
    })
    return render_template("seller_listings.template.html", listings=listings)


@app.route("/update/<listing_id>")
@flask_login.login_required
def show_update(listing_id):
    listing = db.listings.find_one({
        '_id': ObjectId(listing_id)
    })
    car_brand = db.brands.find()
    user = db.listings.find_one({
        '_id': ObjectId(listing_id)
    })
    user_id = user['seller_id']
    if ObjectId(user_id) == flask_login.current_user.account_id:
        return render_template("update_listing.template.html", listing=listing, car_brand=car_brand)
    else:
        return redirect(url_for("show_all_listings"))


@app.route("/update/<listing_id>", methods=["POST"])
@flask_login.login_required
def process_update(listing_id):
    brand_id = request.form.get("car_brand")
    car_model = request.form.get("car_model")
    car_type = request.form.get("car_type")
    car_hp = request.form.get("car_hp")
    car_condition = request.form.get("car_condition")
    car_year = request.form.get("car_year")
    car_price = request.form.get("car_price")
    car_mileage = request.form.get("car_mileage")

    car_brand = db.brands.find_one({
        '_id': ObjectId(brand_id)
    })

    listing = db.listings.find_one({
        '_id': ObjectId(listing_id)
    })

    db.listings.update_one({
        '_id': ObjectId(listing_id)
    },
        {
        '$set': {
            'car': {
                '_id': ObjectId(brand_id),
                'car_brand': car_brand["brand"],
                'car_model': car_model,
                'car_type': car_type,
                'car_hp': car_hp,
                'car_condition': car_condition,
                'car_year': car_year,
                'car_price': car_price,
                'car_mileage': car_mileage
            }
        }
    })
    return redirect(url_for('show_updated', listing_id=listing_id))


@app.route("/updated/<listing_id>")
@flask_login.login_required
def show_updated(listing_id):
    car_brand = db.brands.find()
    listing = db.listings.find_one({
        '_id': ObjectId(listing_id)
    })
    return render_template("updated_listing.template.html", listing=listing)


@app.route("/delete/<listing_id>")
@flask_login.login_required
def show_delete_listing(listing_id):
    listing = db.listings.find_one({
        '_id': ObjectId(listing_id)
    })
    return render_template("delete_listing.template.html", listing=listing)


@app.route("/delete/<listing_id>", methods=["POST"])
@flask_login.login_required
def process_delete_listing(listing_id):
    db.listings.remove({
        '_id': ObjectId(listing_id)
    })
    return redirect(url_for("show_all_listings"))


@app.route('/search')
def search():

    # get all the search terms
    # reminder: if the method is "GET", we retrieve the fields by accessing
    # request.args
    car_seller_name = request.args.get('car_seller_name') or ''
    car_brand_name = request.args.get('car_brand_name') or ''
    car_model_name = request.args.get('car_model_name') or ''
    car_condition = request.args.get('car_condition') or ''

    # create the query base on the search terms
    critera = {}

    if car_seller_name:
        critera['seller_name'] = {
            '$regex': car_seller_name,
            '$options': 'i'
        }

    # if required_country:
    #     critera['address.country'] = {
    #         '$regex': required_country,
    #         '$options': 'i'
    #     }

    # calculate how many results to skip depending the page number

    if len(critera) != 0:
        number_of_results = client[DB_NAME].listings.find(
            critera).count()
        page_size = 1
        number_of_pages = math.ceil(number_of_results / page_size) - 1
        page_number = request.args.get('page_number') or '0'
        page_number = int(page_number)
        number_to_skip = page_number * page_size
        listings = client[DB_NAME].listings.find(
            critera).skip(number_to_skip).limit(page_size)

    else:
        listings = []
        page_number = 0
        number_of_pages = 0
        number_of_results = 0

    return render_template('search.template.html', listings=listings, page_number=page_number,
                           number_of_pages=number_of_pages,
                           car_seller_name=car_seller_name,
                           number_of_results=number_of_results)


# "magic code" -- boilerplate
if __name__ == '__main__':
    app.run(host=os.environ.get('IP'),
            port=int(os.environ.get('PORT')),
            debug=True)
