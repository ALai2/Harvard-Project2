from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import mkdtemp
import time

from helpers import *

import os
import psycopg2

# configure application
app = Flask(__name__)

# ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# custom filter
app.jinja_env.filters["usd"] = usd

# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# configure CS50 Library to use SQLite database
db = SQL(os.environ.get("DATABASE_URL") or "sqlite:///finance.db")

@app.route("/")
@login_required
def index():
    u_row = db.execute("SELECT * FROM users WHERE id=:id", id=session['user_id'])
    username = u_row[0]['username']
    cash = u_row[0]['cash']
    
    result = db.execute("SELECT * FROM portfolio WHERE username=:username", username=username)
    
    if result:
        dict = {}
        dict['symbol'] = []
        dict['name'] = []
        dict['shares'] = []
        dict['price'] = []
        dict['total'] = []

        final_total = 0
        
        for row in result:
            symbol = row['symbol']
            shares = row['shares']
            
            quote = lookup(symbol)
            name = quote['name']
            price = quote['price']
            total = shares * price
            
            dict['symbol'].append(symbol)
            dict['name'].append(name)
            dict['shares'].append(shares)
            dict['price'].append(usd(price))
            dict['total'].append(usd(total))
            
            final_total = final_total + total
    
        length = len(dict['symbol'])
        
        final_total = final_total + cash
    
        return render_template("index.html",length=length,dict=dict, cash=usd(cash), total=usd(final_total))
    else:
        return render_template("index.html",length=0, dict=[], cash=usd(cash), total=usd(cash))

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock."""
    
    if request.method == "POST":
        if not request.form.get('symbol'):
            return apology('must provide symbol')
        
        if not request.form.get('shares'):
            return apology('must provide shares')
        
        symbol = (request.form.get("symbol")).upper()
        quote = lookup(symbol)
        
        if not quote:
            return apology("Invalid Symbol")
        
        price = usd(quote["price"])
        
        shares = int(request.form.get('shares'))
        
        if shares <= 0:
            return apology('shares not positive')
        
        row = db.execute("SELECT * FROM users WHERE id= :id", id=session["user_id"])
        cash = row[0]['cash']
        
        total = shares * quote['price']
        
        if cash - total < 0:
            return apology('cannot afford')
        
        db.execute("UPDATE users SET cash=:cash WHERE id=:id", cash=(cash-total), id=session['user_id'])
        
        username = row[0]['username']
        
        #current_time = time.strftime("%H:%M:%S %m/%d/%Y")
        current_time = time.asctime( time.localtime(time.time()) )
        
        result = db.execute("SELECT * FROM portfolio WHERE symbol=:symbol AND username=:username", symbol=symbol, username=username)
        
        if result:
            old_shares = result[0]['shares']
            new_shares = old_shares + shares
            db.execute("UPDATE portfolio SET shares=:shares WHERE symbol=:symbol AND username=:username", shares=new_shares, symbol=symbol, username=username)
        else:
            db.execute("INSERT INTO portfolio (username, symbol, shares) VALUES (:username, :symbol, :shares)", username=username,symbol=symbol,shares=shares)
        
        db.execute("INSERT INTO history (username, time, symbol, shares) VALUES (:username, :time, :symbol, :shares)", username=username,time=current_time,symbol=symbol,shares=shares)
        
        # redirect user to home page
        return redirect(url_for("index"))
    
    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("buy.html")

@app.route("/history")
@login_required
def history():
    """Show history of transactions."""
    
    u_row = db.execute("SELECT * FROM users WHERE id=:id", id=session['user_id'])
    username = u_row[0]['username']
    
    result = db.execute("SELECT * FROM history WHERE username=:username", username=username)
    
    if result:
        dict = {}
        dict['symbol'] = []
        dict['shares'] = []
        dict['price'] = []
        dict['time'] = []
        
        for row in result:
            symbol = row['symbol']
            shares = row['shares']
            time = row['time']
            
            quote = lookup(symbol)
            name = quote['name']
            price = quote['price']
            total = shares * price
            
            dict['symbol'].append(symbol)
            dict['shares'].append(shares)
            dict['price'].append(usd(price))
            dict['time'].append(time)
    
        length = len(dict['symbol'])
    
        return render_template("history.html",length=length,dict=dict)
    
    else:
        return render_template("history.html",length=0,dict=[])

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        # ensure username exists and password is correct
        if len(rows) != 1 or not pwd_context.verify(request.form.get("password"), rows[0]["hash"]):
            return apology("invalid username and/or password")

        # remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out."""

    # forget any user_id
    session.clear()

    # redirect user to login form
    return redirect(url_for("login"))

@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    
    if request.method == "POST":
        if not request.form.get("symbol"):
            return apology("Enter symbol")
        
        symbol = request.form.get("symbol")
        quote = lookup(symbol)
        
        if not quote:
            return apology("Invalid Symbol")
        
        price = usd(quote["price"])
        
        return render_template("quoted.html", quote=quote, price=price)
    
    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("quote.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password") or not request.form.get("password2"):
            return apology("must provide password")
        
        # query database for username
        result = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))
        
        if result:
            return apology("invalid username")
        
        if request.form.get("password") != request.form.get("password2"):
            return apology("passwords do not match")
        
        # create hash
        hash = pwd_context.hash(request.form.get("password"))
        
        # create new user
        db.execute("INSERT INTO users (username,hash) VALUES (:username,:hash)", username=request.form.get("username"), hash=hash)

        # remember which user has logged in
        row = db.execute("SELECT * FROM users WHERE username= :username", username=request.form.get("username"))
        user_id = row[0]['id']
        session["user_id"] = user_id

        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock."""
    
    if request.method == "POST":
        if not request.form.get('symbol'):
            return apology('must provide symbol')
        
        if not request.form.get('shares'):
            return apology('must provide shares')
        
        symbol = (request.form.get("symbol")).upper()
        
        row = db.execute("SELECT * FROM users WHERE id=:id", id=session['user_id'])
        username = row[0]['username']
        
        result = db.execute("SELECT * FROM portfolio WHERE symbol=:symbol AND username=:username", symbol=symbol, username=username)
        if not result:
            return apology('no symbol available')
        
        shares = int(request.form.get('shares'))
        
        if shares <= 0:
            return apology('shares not positive')
        
        row = db.execute("SELECT * FROM portfolio WHERE symbol=:symbol AND username=:username", symbol=symbol, username=username)
        old_shares = row[0]['shares']
        
        if shares > old_shares:
            return apology('number exceeds available shares')
        
        new_shares = old_shares - shares
        
        if new_shares == 0:
            db.execute("DELETE FROM portfolio WHERE symbol=:symbol AND username=:username", symbol=symbol, username=username)
        else:
            db.execute("UPDATE portfolio SET shares=:shares WHERE symbol=:symbol AND username=:username", shares=new_shares, symbol=symbol, username=username)
        
        quote = lookup(symbol)
        price = quote['price']
        total_p = price * shares
        
        row = db.execute("SELECT * FROM users WHERE id=:id", id=session['user_id'])
        old_cash = row[0]['cash']
        
        new_cash = old_cash + total_p
        
        db.execute("UPDATE users SET cash=:cash WHERE id=:id", cash=new_cash, id=session['user_id'])
        
        #current_time = time.strftime(time.localtime("%H:%M:%S %m/%d/%Y"))
        current_time = time.asctime( time.localtime(time.time()) )
        db.execute("INSERT INTO history (username, time, symbol, shares) VALUES (:username, :time, :symbol, :shares)", username=username,time=current_time,symbol=symbol,shares=0-shares)
        
        # redirect user to home page
        return redirect(url_for("index"))
    
    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("sell.html")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)