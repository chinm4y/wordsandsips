from datetime import datetime
from random import randint
import os
from re import S
from flask  import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
import pyrebase
import secrets
from functools import wraps
from flask_cors import CORS
import pandas as pd


app = Flask(__name__)
app.secret_key = "sgdfsgfsgfdgfgdgfgfdgsdf"

CORS(app)

#Connecting Database to app 
firebaseConfig = {
  "apiKey": "AIzaSyCGuEitG3Xd0czAG2wzVXONANGrocCfMws",
  "authDomain": "words-and-sips.firebaseapp.com",
  "databaseURL": "https://words-and-sips-default-rtdb.asia-southeast1.firebasedatabase.app",
  "projectId": "words-and-sips",
  "storageBucket": "words-and-sips.appspot.com",
  "messagingSenderId": "636972441572",
  "appId": "1:636972441572:web:8a62641e6b9664c3d071f1",
  "measurementId": "G-64L58BNDME",
}

firebase = pyrebase.initialize_app(firebaseConfig)
db = firebase.database()


# Check if user logged in
def is_admin(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'logged_in' in session:
            if session['type'] == 'admin':
                return f(*args, **kwargs)
        else:
            flash('Please Login First', 'secondary')
            return redirect(url_for('login'))
    return wrap


# Check if user logged in
def is_logged_in(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'logged_in' in session:
            return f(*args, **kwargs)
        else:
            flash('Please Login First', 'secondary')
            return redirect(url_for('login'))
    return wrap


@app.route('/') 
def index():
    return render_template("index.html")

@app.route('/checkout') 
def checkout():
    cart_dict = session["cart"]["products"]
    cart = []
    total = 0
    for product_id in list(cart_dict.keys()):
        pro = db.child("menu").child(product_id).get().val()
        cart.append({
            "product_id": product_id,
            "name": pro.get("name"),
            "quantity": int(cart_dict[product_id]),
            "amount": int(pro.get("price")) * int(cart_dict[product_id]),
            "category": pro.get("category")
        })
        total += int(pro.get("price")) * int(cart_dict[product_id])
    return render_template("checkout.html", cart=cart, total=total)


@app.route('/remove_from_cart/<string:product_id>')
def remove_from_cart(product_id):
    product = db.child("menu").child(product_id).get().val()
    price = product["price"]
    session["cart"]["cart_total"] -= int(price) * int(session["cart"]["products"][product_id])
    del session["cart"]["products"][product_id]
    flash("Item deleted from cart!", "info")
    return redirect(url_for("checkout"))


@app.route('/confirm_order')
def confirm_order():
    cart_dict = session["cart"]["products"]
    cart = []
    date = session["start_time"].split(" ")[0]
    orders = db.child("orders").order_by_child("type").equal_to("tab").get().val()
    users = db.child("users").order_by_child("type").equal_to("tab").get().val()


    for product_id in list(cart_dict.keys()):
        pro = db.child("menu").child(product_id).get().val()
        amount = int(pro.get("price")) * int(cart_dict[product_id])
        cart.append({
            "product_id": product_id,
            "name": pro.get("name"),
            "quantity": int(cart_dict[product_id]),
            "amount": amount,
            "category": pro.get("category"),
        })

        kflag, cflag, pflag = 0, 0, 0
        if db.child("sales").child(date).shallow().get().val():
            result = db.child("sales").child(date).get().val()
            if pro.get("category") in result.keys():
                result1 = db.child("sales").child(date).child(pro.get("category")).get().val()
                if pro.get("name") in result1.keys():
                    prod = db.child("sales").child(date).child(pro.get("category")).child(pro.get("name")).get().val()
                    prod = prod + int(cart_dict[product_id])
                    db.child("sales").child(date).child(pro.get("category")).child(pro.get("name")).set(prod)
                else:
                    pflag = 1
            else:
                cflag = 1
        else:
            kflag = 1

        if kflag == 1 or cflag==1 or pflag ==1:
            db.child("sales").child(date).child(pro.get("category")).child(pro.get("name")).set(int(cart_dict[product_id]))
        
        for u in users.keys():
            totals = []
                # print(users[u]["email"])
            for id in orders:
                if users[u]["email"] == orders[id]["email"]:
                    totals.append(orders[id]["total"])
                print(totals)
                total_total = sum(totals)
                print(total_total)

                userdata = db.child("users").child(u).get().val()
                userdata.update({"total_total": total_total})
                db.child("users").child(u).set(userdata)
            else:
                continue

    order_id = randint(1, 99999)
    cart.append({
        "entry_fee": session["service_charge"]
    })
    total = session["service_charge"]
    if session["cart"]["cart_total"] > session["service_charge"]:
        total += session["cart"]["cart_total"] - session["service_charge"]
    if session["type"] == "tab":
        # prev_data = db.child("orders").order_by_child("email").equal_to(session["email"])
        # print("PREVIOUS DATA: ", prev_data)
        data = {
            "name": session["name"],
            "email": session["email"],
            "order_no": order_id,
            "order": cart,
            "total": total,
            'location': session["location"],
            "start_time": session["start_time"],
            "status": "OPEN",
            "table": session["table"],
            "type": session["type"]
        }
        data.update({"quantity": session["quantity"]})

    else:
        data = {
            "name": session["name"],
            "order_no": order_id,
            "order": cart,
            "total": total,
            'location': session["location"],
            "start_time": session["start_time"],
            "status": "OPEN",
            "table": session["table"],
            "type": session["type"]
        }
    data.update({"quantity": session["quantity"]})
    res = db.child("orders").push(data)
    session["cart"] = {"products": {}, "cart_total": 0}
    session["service_charge"] = 0
    print(res)
    flash("Order placed", "success")
    return redirect(url_for("menu"))


@app.route('/add_product/<string:order_id>')
def add_product(order_id):
    all_order = dict(db.child("orders").child(order_id).get().val())
    orders = all_order["order"] 
    print(all_order)
    pro = {
        "name": "Cigarettes",
        "amount": 20,
        "quantity": 1
    }
    for order in orders:
        if order.get("name") == "Cigarettes":
            order["quantity"] += 1
            order["amount"] += 20
            all_order["total"] += 20

            break
    else:
        orders.append(pro)
        all_order["total"] += 20
    print(orders)
    res = db.child("orders").child(order_id).set(all_order)

    flash("Product addedd successfully", "success")
    return redirect(url_for("dashboard"))

@app.route("/update_quantity/<product_id>/<quantity>")
def update_product_quantity(product_id, quantity):
    if "cart" in session:
        print("OLD CART:", session["cart"])
        product_dict = session["cart"]["products"]
        product_dict[product_id] = quantity
        cart_total = 0
        for product_id, quantity in product_dict.items():
            product = db.child("menu").child(product_id).get().val()
            price = product["price"]
            cart_total += int(price) * int(quantity)
        session["cart"]["cart_total"] = cart_total
        print("NEW CART:", session["cart"])
        session["cart"] = {"products": product_dict, "cart_total": cart_total}
        flash("Quantity updated!", "info")
    return redirect(url_for("checkout"))


@app.route('/checkin', methods = ['GET','POST'])
def checkin():
    if request.method == 'POST':
        name = request.form['name']
        phone = request.form['phone']
        location = request.form['location']
        table = request.form['table']
        quantity = int(request.form['quantity'])
        start_time = request.form['start_time']
        data = {
            "name": name,
            "phone": phone,
            "type":'customer',
            "location": location,
            "table": table,
            "quantity": quantity,
            "start_time": start_time
        }
        results = db.child("users").push(data)
        session["name"] = name
        session["phone"] = phone
        session["id"] = results["name"]
        session['location'] = location
        session['table'] = table
        session["cart"] = {"products": {}, "cart_total":0}
        session["quantity"] = quantity
        session["start_time"] = start_time
        session["type"] = "customer"
        session["service_charge"] = 100 * quantity
        return redirect(url_for('menu'))


@app.route('/manage_tabs', methods=["GET", "POST"])
@is_logged_in
def manage_tabs():
    orders = db.child("orders").order_by_child("type").equal_to("tab").get().val()

    users = db.child("users").order_by_child("type").equal_to("tab").get().val()

    if users:
        emails = set()
        for order in orders:
            emails.add(orders[order]["email"])

        customers = {}
        for email in emails:
            for order in orders:
                if orders[order]["email"] == email:
                    customers[email] = orders[order]["name"]

        # total_total = 0

        # print(users.keys())

        # for u in users.keys():
        #     print(u)
        #     totals = []
        #     for id in orders:
        #         if users[u]["email"] == orders[id]["email"]:
        #             totals.append(orders[id]["total"])
        #         # print(totals)
        #         total_total = sum(totals)
        #     # print(total_total)
            
        #     # try:
        #     userdata = db.child("users").child(u).get().val()
        #     userdata.update({"total_total": total_total})
        #     db.child("users").child(u).set(userdata)
        # except:
            # continue
    
        return render_template("managetabs.html",users=users, orders=orders, customers=customers)

    else:
        return render_template("managetabs.html")


@app.route('/change_total/<customer>', methods=["POST"])
def change_total(customer):
    orders = db.child("orders").order_by_child("type").equal_to("tab").get().val()

    emails = set()
    for order in orders:
        emails.add(orders[order]["email"])
    
    customers = {}
    for email in emails:
        for order in orders:
            if orders[order]["email"] == email:
                customers[email] = orders[order]["name"]

    print(customer)
    data = request.form.get("dep")
    print(data)
    users = db.child("users").order_by_child("type").equal_to("tab").get().val()

    for u in users.keys():
        if users[u]["email"] == customer:
            customer_id = u
    
    print(customer_id)
    
    tot = db.child("users").child(customer_id).child("total_total").get().val()
    print(tot)
    total_total = tot-data

    db.child("users").child(customer_id).update({"total_total": total_total})
    # userdata.update({"total_total": total_total})
    # db.child("users").child(customer_id).set(userdata)


    return render_template("managetabs.html", users=users, orders=orders, customers=customers)


@app.route('/menu')
def menu():
    menu  = db.child("menu").get().val()
    categories = set([menu[item]["category"] for item in menu])
    return render_template("menu.html", menu=menu, categories=categories)


@app.route('/manage_menu', methods=['GET', 'POST'])
def manage_menu():
    if request.method == "POST":
        category = request.form.get("category")
        item_name = request.form.get("item_name")
        active_status = bool(request.form.get("active_status"))
        price = int(request.form.get("price"))
        data = {"active": active_status,
        "name": item_name,
        "category": category,
        "price": price}
        res = db.child("menu").push(data)
        flash("Product successfully added!", "success")
   

    menu  = db.child("menu").get().val()
    return render_template("manage_menu.html", menu = menu)

@app.route("/delete_menu/<id>")
def delete_menu(id):
    print(id)
    res = db.child("menu").child(id).remove()
    flash("Deleted successfully", "success")
    return jsonify({
        "success": True
    })


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        admin = db.child("admin").get().val()
        user = db.child("users").order_by_child("email").equal_to(email).get().val()
        print(user)
        if admin:
            if email == admin["email"] and password == admin["password"]:
                session["logged_in"] = True
                session["email"] = email
                session['type'] = 'admin'
                print('password matched')
                return redirect(url_for('dashboard'))
        if user:
            u = list(dict(user).values())[0]
            if email == u["email"] and password == u["password"]:
                session["logged_in"] = True
                session["email"] = email
                session['type'] = 'tab'
                session["name"] = u["name"]
                print(u)
                print('password matched')
                return redirect(url_for('tab_checkin'))
        


    return render_template("login.html")


@app.route('/admin/dashboard', methods=['GET', 'POST'])
@is_admin
def dashboard():
    orders = db.child("orders").order_by_child("status").equal_to("OPEN").get().val()
    return render_template("dashboard.html", orders=orders)


@app.route('/checkout_order/<string:order_id>', methods=['GET', 'POST'])
def checkout_order(order_id):
    order = db.child("orders").child(order_id).update({"status": "CLOSED"})
    print(order)
    return redirect(url_for("dashboard"))


@app.route('/order_history')
def order_history():
    orders = db.child("orders").order_by_child("status").equal_to("CLOSED").get().val()
    new_orders = {}
    total = 0
    if orders:
        for id in orders.keys():
            if orders[id]["type"] != "tab":
                new_orders[id] = orders[id]
                total += orders[id]["total"]

    # print(type(orders))
    # print("ORDERS: ", orders)
    # for id in orders:
    #     keys = list(orders[id].keys())
    #     keys.remove("location")
    #     keys.remove("quantity")
    #     keys.remove("status")
    #     keys.remove("table")

    # print(keys)
    
    # for order in orders:
    #     print(orders[order])
    #     print(type(orders))


    # df = pd.DataFrame(orders, columns=keys())
    # print(df)
    return render_template("order_history.html", orders=new_orders, total=total)
    
@app.route('/delete_users')
def delete_users():
    users = db.child("users").get().val()
    if users:
        for id in users.keys():
            db.child(f"users/{id}").remove() if users[id]["type"]=='customer' else None
        flash("deleted", "success")
    else:
        flash("No users", "info")
    return redirect(url_for("order_history"))

@app.route('/delete_orders')
def delete_orders():
    orders = db.child("orders").get().val()
    if orders:
        for id in orders.keys():
            db.child(f"orders/{id}").remove() if orders[id]["type"]=='customer' and orders[id]["status"] == "CLOSED" else None
        flash("deleted", "success")
    else:
        flash("No orders", "info")
    return redirect(url_for("order_history"))

@app.route('/view_sales', methods=["GET", "POST"])
def view_sales():
    sales = db.child("sales").get().val()
    if request.method == "POST":
        date = request.form.get("date")
        # print(date)
        sale = db.child("sales").child(date).get().val()
        print(sale)

       
    # print(sales)
        return render_template("sales.html", sales = sales, sale = sale, date= date)
    else:
        print(sales.keys())
        return render_template("sales.html", sales = sales)

@app.route('/delete_order/<string:id>')
def delete_order(id):
    db.child("orders").child(id).remove()
    return redirect(url_for("manage_tabs"))

@app.route('/add_member', methods=["POST"])
def add_member():
    name = request.form.get("name")
    email = request.form.get("email")
    password = request.form.get("password")
    res = db.child("users").push({
        "name": name,
        "email": email,
        "password": password,
        "type": "tab",
        "total_total": 0
    })
    flash("Added successfully", "success")
    return redirect(url_for("manage_tabs"))

@app.route('/to_csv')
def to_csv():
    orders = db.child("orders").order_by_child("status").equal_to("CLOSED").get().val()
    # print(orders)

    df = pd.DataFrame(orders)
    # print(df)
    # today = datetime.now()
    # file = str(today.year) + "/" + str(today.month) + "/" + str(today.day) + "/" + str(today.hour) + ":" + str(today.minute)
    df.to_csv("data.csv")
    return send_file("data.csv", as_attachment=True)
    # return redirect(url_for("order_history"))

@app.route('/admin/logout/')
@is_logged_in
def logout():
    if 'logged_in' in session:
        session.clear()
        flash('Successfully logged out','success')
        return redirect(url_for('login'))
    else:
        flash('You are not Logged in','secondary')
        return redirect(url_for('login'))


@app.route('/add_to_cart/<string:product_id>')
def add_to_cart(product_id):
    item  = db.child("menu").child(product_id).get().val()
    if "cart" in session:
        product_dict = session["cart"]["products"]
        if product_id in product_dict:
            # add number
            product_dict[product_id] += 1
        else:
            # add key value
            product_dict[product_id] = 1
        total_price = int(session["cart"]["cart_total"])
        total_price += int(item["price"])
        session["cart"] = {"products": product_dict, "cart_total": total_price}
    else:
        session["cart"] = {
            "products": {product_id: 1},
            "cart_total": int(item["price"]),
        }
    flash("Added product to cart", "success")
    return redirect(url_for("menu"))


@app.route('/tab_checkin', methods=['GET', 'POST'])
def tab_checkin():
    if request.method == "POST":
        location = request.form['location']
        table = request.form['table']
        quantity = int(request.form['quantity'])
        start_time = request.form['start_time']
        data = {
            "type":'customer',
            "location": location,
            "table": table,
            "quantity": quantity,
            "start_time": start_time
        }
        results = db.child("users").order_by_child("name").equal_to(session["name"]).push(data)
        session["id"] = results["name"]
        session['location'] = location
        session['table'] = table
        session["cart"] = {"products": {}, "cart_total":0}
        session["quantity"] = quantity
        session["start_time"] = start_time
        session["service_charge"] = 100 * quantity
        return redirect(url_for('menu'))




    return render_template("tab_checkin.html")
    
if __name__ == '__main__':
    app.run(debug=True, port=7001, host="127.0.0.1")
    