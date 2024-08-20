from datetime import date
from flask import Flask, abort, render_template, redirect, url_for, flash
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_gravatar import Gravatar
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user, login_required
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Text, ForeignKey
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from typing import List
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
from datetime import datetime

app = Flask(__name__)
app.config["SECRET_KEY"] = "8BYkEfBA6O6donzWlSihBXox7C0sKR6b"
ckeditor = CKEditor(app)
Bootstrap5(app)

gravatar = Gravatar(app, size=100, rating="g", default="retro", force_default=False, force_lower=False, use_ssl=False, base_url=None)

login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return db.get_or_404(User, user_id)

year = datetime.now().year

# CREATE DATABASE
class Base(DeclarativeBase):
    pass


app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///blog.db"
db = SQLAlchemy(model_class=Base)
db.init_app(app)


# CONFIGURE TABLES


# Child - BlogPost
class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    subtitle: Mapped[str] = mapped_column(String(250), nullable=False)
    date: Mapped[str] = mapped_column(String(250), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    img_url: Mapped[str] = mapped_column(String(250), nullable=False)

    # Child with parent 'User'
    author: Mapped["User"] = relationship(back_populates="posts")
    author_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"))

    # Parent with child 'Comment'
    comments: Mapped[List["Comment"]] = relationship(back_populates="post")


# parent - User
class User(UserMixin, db.Model):
    __tablename__ = "user"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(1000), nullable=False)

    # Parent with childs 'BlogPost' and 'Comment'
    posts: Mapped[List["BlogPost"]] = relationship(back_populates="author")
    comments: Mapped[List["Comment"]] = relationship(back_populates="comment_author")

    def __repr__(self):
        return f"<User {self.id}: {self.name}>"


class Comment(db.Model):
    __tablename__ = "comments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    # Child with parent 'User'
    comment_author: Mapped["User"] = relationship(back_populates="comments")
    comment_author_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"))

    # Child with parent 'BlogPost'
    post: Mapped["BlogPost"] = relationship(back_populates="comments")
    post_id: Mapped[int] = mapped_column(Integer, ForeignKey("blog_posts.id"))


with app.app_context():
    db.create_all()


def admin_only(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if current_user.id == 1:
            return func(*args, **kwargs)
        else:
            return abort(403)

    return wrapper


@app.route("/register", methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        new_email = form.email.data
        user = db.session.execute(db.select(User).where(User.email == new_email)).scalar()

        if user:
            flash("You've already signed up with that email, log in instead!")
            return redirect(url_for("login"))

        else:
            new_password = generate_password_hash(form.password.data, method="pbkdf2:sha256", salt_length=8)
            new_name = form.name.data

            with app.app_context():
                new_user = User(email=new_email, password=new_password, name=new_name)
                db.session.add(new_user)
                db.session.commit()

                login_user(new_user)

                return redirect(url_for("get_all_posts"))

    return render_template("register.html", form=form, year=year)


@app.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data

        user = db.session.execute(db.select(User).where(User.email == email)).scalar()

        if not user:
            flash("That email does not exist, please try again.")
            return redirect(url_for("login"))

        elif not check_password_hash(user.password, password):
            flash("Password incorrect, please try again.")
            return redirect(url_for("login"))

        else:
            login_user(user)
            return redirect(url_for("get_all_posts"))

    return render_template("login.html", form=form, year=year)


@app.route("/logout")
def logout():
    if current_user.is_authenticated:
        logout_user()
    return redirect(url_for("get_all_posts"))


@app.route("/")
def get_all_posts():
    print(year)
    result = db.session.execute(db.select(BlogPost))
    posts = result.scalars().all()
    return render_template("index.html", all_posts=posts, year=year)


@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    form = CommentForm()
    requested_post = db.get_or_404(BlogPost, post_id)
    if form.validate_on_submit():
        if current_user.is_authenticated:
            new_comment = Comment(
                text=form.comment_text.data,
                comment_author=current_user,
                post=requested_post,
            )
            db.session.add(new_comment)
            db.session.commit()
            return render_template("post.html", post=requested_post, form=form, year=year)

        else:
            flash("You need to login or register to comment.")
            return redirect(url_for("login"))

    return render_template("post.html", post=requested_post, form=form, year=year)


@app.route("/new-post", methods=["GET", "POST"])
@login_required
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y"),
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form, year=year)


@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@login_required
@admin_only
def edit_post(post_id):
    post = db.get_or_404(BlogPost, post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body,
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = current_user
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))
    return render_template("make-post.html", form=edit_form, is_edit=True, year=year)


@app.route("/delete/<int:post_id>")
@login_required
@admin_only
def delete_post(post_id):
    post_to_delete = db.get_or_404(BlogPost, post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for("get_all_posts"))


@app.route("/about")
def about():
    return render_template("about.html", year=year)


@app.route("/contact")
def contact():
    return render_template("contact.html", year=year)


if __name__ == "__main__":
    app.run(debug=True, port=5002)
