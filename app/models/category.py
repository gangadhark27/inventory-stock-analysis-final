from app.extensions import db

class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False, index=True)
    description = db.Column(db.String(255), nullable=True)

    products = db.relationship("Product", backref="category", lazy="dynamic")

    @property
    def product_count(self) -> int:
        return self.products.filter_by(is_active=True).count()

    def __repr__(self):
        return f"<Category {self.name}>"
