
import os
from pathlib import Path
from decimal import Decimal
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-change-me")
database_url = os.getenv("DATABASE_URL")

if database_url:
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        "sqlite:///" + str(Path(app.instance_path) / "made_in_ghana.db")
    )
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

GHANA_REGIONS = [
    "Greater Accra","Ashanti","Western","Eastern","Central","Northern",
    "Volta","Bono","Bono East","Ahafo","Upper East","Upper West",
    "Oti","Savannah","North East","Western North"
]

class User(db.Model):
    id=db.Column(db.Integer,primary_key=True); name=db.Column(db.String(120),nullable=False)
    email=db.Column(db.String(160),unique=True,nullable=False); password_hash=db.Column(db.String(255),nullable=False)
    role=db.Column(db.String(30),default="customer"); country=db.Column(db.String(80),default="Ghana")
    region=db.Column(db.String(80)); phone=db.Column(db.String(30)); business_name=db.Column(db.String(160))
    business_description=db.Column(db.Text); seller_approved=db.Column(db.Boolean,default=False)
    created_at=db.Column(db.DateTime,server_default=db.func.now())
    products=db.relationship("Product",backref="seller",lazy=True)
    def set_password(self,p): self.password_hash=generate_password_hash(p)
    def check_password(self,p): return check_password_hash(self.password_hash,p)

class Category(db.Model):
    id=db.Column(db.Integer,primary_key=True); name=db.Column(db.String(100),unique=True,nullable=False)
    slug=db.Column(db.String(120),unique=True,nullable=False)

class Product(db.Model):
    id=db.Column(db.Integer,primary_key=True); seller_id=db.Column(db.Integer,db.ForeignKey("user.id"),nullable=False)
    category_id=db.Column(db.Integer,db.ForeignKey("category.id"),nullable=False); name=db.Column(db.String(180),nullable=False)
    description=db.Column(db.Text,nullable=False); price=db.Column(db.Numeric(12,2),nullable=False); wholesale_price=db.Column(db.Numeric(12,2))
    min_wholesale_qty=db.Column(db.Integer,default=5); stock=db.Column(db.Integer,default=0); image_url=db.Column(db.String(500))
    origin=db.Column(db.String(80),default="Ghana"); region=db.Column(db.String(80)); approved=db.Column(db.Boolean,default=False)
    featured=db.Column(db.Boolean,default=False); created_at=db.Column(db.DateTime,server_default=db.func.now())
    category=db.relationship("Category")

class Wishlist(db.Model):
    id=db.Column(db.Integer,primary_key=True); user_id=db.Column(db.Integer,db.ForeignKey("user.id")); product_id=db.Column(db.Integer,db.ForeignKey("product.id"),unique=True)
    product=db.relationship("Product")

class Review(db.Model):
    id=db.Column(db.Integer,primary_key=True); user_id=db.Column(db.Integer,db.ForeignKey("user.id"))
    product_id=db.Column(db.Integer,db.ForeignKey("product.id")); rating=db.Column(db.Integer,nullable=False); comment=db.Column(db.Text)
    user=db.relationship("User"); product=db.relationship("Product")

class Order(db.Model):
    id=db.Column(db.Integer,primary_key=True); user_id=db.Column(db.Integer,db.ForeignKey("user.id"),nullable=False)
    total=db.Column(db.Numeric(12,2),nullable=False); status=db.Column(db.String(40),default="Pending")
    payment_method=db.Column(db.String(50),default="Mobile Money"); phone=db.Column(db.String(30),nullable=False)
    address=db.Column(db.String(300),nullable=False); city=db.Column(db.String(100),nullable=False); region=db.Column(db.String(80))
    created_at=db.Column(db.DateTime,server_default=db.func.now()); user=db.relationship("User",backref="orders")
    items=db.relationship("OrderItem",backref="order",cascade="all, delete-orphan")

class OrderItem(db.Model):
    id=db.Column(db.Integer,primary_key=True); order_id=db.Column(db.Integer,db.ForeignKey("order.id"),nullable=False)
    product_id=db.Column(db.Integer,db.ForeignKey("product.id"),nullable=False); quantity=db.Column(db.Integer,nullable=False)
    price=db.Column(db.Numeric(12,2),nullable=False); product=db.relationship("Product")

def me(): return db.session.get(User,session.get("user_id")) if session.get("user_id") else None
@app.context_processor
def globals(): return {"current_user":me(),"cart_count":sum(session.get("cart",{}).values()),"regions":GHANA_REGIONS}
def need_login(f):
    @wraps(f)
    def w(*a,**k):
        if not me(): flash("Please log in first.","warning"); return redirect(url_for("login",next=request.path))
        return f(*a,**k)
    return w
def need_seller(f):
    @wraps(f)
    def w(*a,**k):
        u=me()
        if not u or u.role not in ("seller","admin") or (u.role=="seller" and not u.seller_approved):
            flash("You need an approved Ghanaian seller account.","warning"); return redirect(url_for("seller_register"))
        return f(*a,**k)
    return w
def need_admin(f):
    @wraps(f)
    def w(*a,**k):
        if not me() or me().role!="admin": flash("Admin access required.","danger"); return redirect(url_for("index"))
        return f(*a,**k)
    return w

@app.route("/")
def index():
    return render_template("index.html",products=Product.query.filter_by(approved=True).order_by(Product.featured.desc(),Product.id.desc()).limit(12).all(),categories=Category.query.all())

@app.route("/shop")
def shop():
    q=request.args.get("q","").strip(); cat=request.args.get("category",""); region=request.args.get("region",""); mode=request.args.get("mode","")
    query=Product.query.filter_by(approved=True)
    if q: query=query.filter(db.or_(Product.name.ilike(f"%{q}%"),Product.description.ilike(f"%{q}%")))
    if cat: query=query.join(Category).filter(Category.slug==cat)
    if region: query=query.filter(Product.region==region)
    if mode=="wholesale": query=query.filter(Product.wholesale_price.isnot(None))
    return render_template("shop.html",products=query.order_by(Product.featured.desc(),Product.id.desc()).all(),categories=Category.query.all(),q=q,cat=cat,region=region,mode=mode)

@app.route("/product/<int:product_id>",methods=["GET","POST"])
def product(product_id):
    p=Product.query.get_or_404(product_id)
    if not p.approved and (not me() or me().role!="admin"): return redirect(url_for("shop"))
    if request.method=="POST" and me():
        rating=max(1,min(5,int(request.form["rating"])))
        db.session.add(Review(user_id=me().id,product_id=p.id,rating=rating,comment=request.form.get("comment","").strip())); db.session.commit()
        flash("Review added.","success"); return redirect(url_for("product",product_id=p.id))
    reviews=Review.query.filter_by(product_id=p.id).order_by(Review.id.desc()).all()
    avg=round(sum(x.rating for x in reviews)/len(reviews),1) if reviews else 0
    return render_template("product.html",product=p,reviews=reviews,avg=avg)

@app.route("/seller/<int:user_id>")
def seller_store(user_id):
    seller=User.query.get_or_404(user_id)
    products=Product.query.filter_by(seller_id=seller.id,approved=True).all()
    return render_template("seller_store.html",seller=seller,products=products)

@app.route("/register",methods=["GET","POST"])
def register():
    if request.method=="POST":
        email=request.form["email"].strip().lower()
        if User.query.filter_by(email=email).first(): flash("Email already registered.","danger")
        else:
            u=User(name=request.form["name"].strip(),email=email,country="Ghana",region=request.form.get("region"),phone=request.form.get("phone"))
            u.set_password(request.form["password"]); db.session.add(u); db.session.commit(); session["user_id"]=u.id
            flash("Welcome to Made in Ghana.","success"); return redirect(url_for("index"))
    return render_template("auth.html",mode="register")

@app.route("/login",methods=["GET","POST"])
def login():
    if request.method=="POST":
        u=User.query.filter_by(email=request.form["email"].strip().lower()).first()
        if u and u.check_password(request.form["password"]): session["user_id"]=u.id; return redirect(request.args.get("next") or url_for("index"))
        flash("Invalid login.","danger")
    return render_template("auth.html",mode="login")
@app.route("/logout")
def logout(): session.clear(); return redirect(url_for("index"))

@app.route("/seller/register",methods=["GET","POST"])
@need_login
def seller_register():
    u=me()
    if request.method=="POST":
        if not u.region: flash("Add your Ghana region to your account first.","warning")
        else:
            u.role="seller"; u.business_name=request.form["business_name"].strip(); u.business_description=request.form["business_description"].strip(); u.seller_approved=False
            db.session.commit(); flash("Seller application submitted for review.","success"); return redirect(url_for("seller_dashboard"))
    return render_template("seller_register.html",user=u)

@app.route("/seller")
@need_seller
def seller_dashboard(): return render_template("seller_dashboard.html",products=Product.query.filter_by(seller_id=me().id).order_by(Product.id.desc()).all())

@app.route("/seller/product/new",methods=["GET","POST"])
@need_seller
def seller_product_new():
    if request.method=="POST":
        p=Product(seller_id=me().id,category_id=int(request.form["category_id"]),name=request.form["name"].strip(),description=request.form["description"].strip(),
        price=Decimal(request.form["price"]),wholesale_price=Decimal(request.form["wholesale_price"]) if request.form.get("wholesale_price") else None,
        min_wholesale_qty=int(request.form.get("min_wholesale_qty") or 5),stock=int(request.form["stock"]),image_url=request.form.get("image_url","").strip(),region=me().region)
        db.session.add(p); db.session.commit(); flash("Product submitted for approval.","success"); return redirect(url_for("seller_dashboard"))
    return render_template("product_form.html",categories=Category.query.all())

@app.post("/wishlist/<int:product_id>")
@need_login
def wishlist(product_id):
    existing=Wishlist.query.filter_by(user_id=me().id,product_id=product_id).first()
    if existing: db.session.delete(existing); flash("Removed from wishlist.","success")
    else: db.session.add(Wishlist(user_id=me().id,product_id=product_id)); flash("Added to wishlist.","success")
    db.session.commit(); return redirect(request.referrer or url_for("shop"))
@app.route("/wishlist")
@need_login
def wishlists(): return render_template("wishlist.html",items=Wishlist.query.filter_by(user_id=me().id).all())

@app.post("/cart/add/<int:product_id>")
def cart_add(product_id):
    p=Product.query.get_or_404(product_id)
    if not p.approved or p.stock<1: flash("Unavailable.","danger"); return redirect(url_for("shop"))
    cart=session.setdefault("cart",{}); k=str(product_id); cart[k]=min(cart.get(k,0)+int(request.form.get("quantity",1)),p.stock); session.modified=True
    flash("Added to cart.","success"); return redirect(request.referrer or url_for("shop"))
@app.post("/cart/remove/<int:product_id>")
def cart_remove(product_id):
    c=session.get("cart",{}); c.pop(str(product_id),None); session["cart"]=c; return redirect(url_for("cart"))
@app.route("/cart")
def cart():
    items=[]; total=Decimal("0")
    for pid,qty in session.get("cart",{}).items():
        p=db.session.get(Product,int(pid))
        if p and p.approved:
            sub=p.price*qty; total+=sub; items.append((p,qty,sub))
    return render_template("cart.html",items=items,total=total)

@app.route("/checkout",methods=["GET","POST"])
@need_login
def checkout():
    items=[]; total=Decimal("0")
    for pid,qty in session.get("cart",{}).items():
        p=db.session.get(Product,int(pid))
        if p and p.approved and qty<=p.stock: sub=p.price*qty; total+=sub; items.append((p,qty,sub))
    if not items: flash("Your cart is empty.","warning"); return redirect(url_for("shop"))
    if request.method=="POST":
        o=Order(user_id=me().id,total=total,payment_method=request.form["payment_method"],phone=request.form["phone"],address=request.form["address"],city=request.form["city"],region=request.form["region"],status="Pending Payment" if request.form["payment_method"]!="Cash on Delivery" else "Processing")
        db.session.add(o); db.session.flush()
        for p,q,s in items: p.stock-=q; db.session.add(OrderItem(order_id=o.id,product_id=p.id,quantity=q,price=p.price))
        db.session.commit(); session["cart"]={}; flash("Order placed successfully.","success"); return redirect(url_for("order_detail",order_id=o.id))
    return render_template("checkout.html",items=items,total=total,user=me())

@app.route("/orders")
@need_login
def orders(): return render_template("orders.html",orders=Order.query.filter_by(user_id=me().id).order_by(Order.id.desc()).all())
@app.route("/order/<int:order_id>")
@need_login
def order_detail(order_id):
    o=Order.query.get_or_404(order_id)
    if o.user_id!=me().id and me().role!="admin": return redirect(url_for("orders"))
    return render_template("order_detail.html",order=o)

@app.route("/admin")
@need_admin
def admin(): return render_template("admin.html",pending_sellers=User.query.filter_by(role="seller",seller_approved=False).all(),pending_products=Product.query.filter_by(approved=False).all(),orders=Order.query.order_by(Order.id.desc()).limit(30).all())
@app.post("/admin/seller/<int:user_id>/approve")
@need_admin
def approve_seller(user_id): u=User.query.get_or_404(user_id); u.seller_approved=True; db.session.commit(); return redirect(url_for("admin"))
@app.post("/admin/product/<int:product_id>/approve")
@need_admin
def approve_product(product_id): p=Product.query.get_or_404(product_id); p.approved=True; db.session.commit(); return redirect(url_for("admin"))
@app.post("/admin/order/<int:order_id>/status")
@need_admin
def order_status(order_id): o=Order.query.get_or_404(order_id); o.status=request.form["status"]; db.session.commit(); return redirect(url_for("admin"))

@app.get("/api/health")
def health(): return jsonify(status="ok",app="Made in Ghana",currency="GHS",country="Ghana")

def seed():
    db.create_all()
    cats=[("Fashion & Clothing","fashion"),("Food & Beverages","food"),("Beauty & Personal Care","beauty"),("Handmade & Crafts","crafts"),("Home & Living","home"),("Electronics & Gadgets","electronics"),("Agriculture","agriculture"),("Books & Education","books"),
        ("Construction","construction"),("Carpentry","carpentry")]
    for n,s in cats:
        if not Category.query.filter_by(slug=s).first(): db.session.add(Category(name=n,slug=s))
    admin_email = os.getenv("ADMIN_EMAIL")
    admin_password = os.getenv("ADMIN_PASSWORD")

    if admin_email and admin_password and not User.query.filter_by(email=admin_email).first():
        u = User(
            name="Made in Ghana Admin",
            email=admin_email,
            role="admin",
            country="Ghana",
            region="Greater Accra",
            seller_approved=True
        )
        u.set_password(admin_password)
        db.session.add(u)
    db.session.commit()

with app.app_context():
    seed()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG", "0") == "1"
    )
