# Made in Ghana — E-commerce Marketplace

A mobile-friendly Ghana-focused marketplace for locally made products.

## Main features
- Ghana-only marketplace concept
- Customer registration/login
- Seller registration
- Seller dashboard
- Product creation/editing
- Categories and search
- Product detail pages
- Cart and checkout
- Order history
- Admin dashboard
- Product/seller approval workflow
- Ghana Cedi (GHS) pricing
- Mobile Money / card checkout placeholder
- Optional Paystack integration
- Responsive UI suitable for Android browsers and Termux

## Run in Termux

```bash
pkg update
pkg install python
cd ~/made_in_ghana
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python app.py
```

Open:
http://127.0.0.1:5000

For LAN access:
http://YOUR_PHONE_IP:5000

## Default admin
On first run, an admin account is created:
- email: admin@madeinghana.local
- password: ChangeMe123!

Change the password before real deployment.

## Important
This starter project does not claim to verify that every product is genuinely Ghana-made automatically. The admin approval workflow is provided so products and sellers can be reviewed before being marked approved.

For live payments, add your own Paystack keys to `.env` and complete the production webhook/security configuration.
