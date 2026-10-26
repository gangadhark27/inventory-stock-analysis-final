from decimal import Decimal
from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    PasswordField,
    BooleanField,
    SelectField,
    IntegerField,
    DecimalField,
    TextAreaField,
    SubmitField,
    DateField
)
from wtforms.validators import (
    DataRequired,
    Length,
    NumberRange,
    Optional,
    Email,
    Regexp
)
from app.models.user import Role


class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(min=3, max=50)])
    password = PasswordField("Password", validators=[DataRequired()])
    remember = BooleanField("Remember Me")
    submit = SubmitField("Sign In")


class UserForm(FlaskForm):
    username = StringField(
        "Username",
        validators=[
            DataRequired(),
            Length(min=3, max=50),
            Regexp(r"^[a-zA-Z0-9_.-]+$", message="Username must contain only letters, numbers, dots, hyphens, and underscores.")
        ]
    )
    full_name = StringField("Full Name", validators=[DataRequired(), Length(min=2, max=100)])
    role = SelectField("Role", choices=[(Role.ADMIN, "Administrator"), (Role.STAFF, "Staff")], default=Role.STAFF)
    password = PasswordField("Password", validators=[Optional(), Length(min=6, max=100)])
    is_active = BooleanField("Active Account", default=True)
    submit = SubmitField("Save User")


class CategoryForm(FlaskForm):
    name = StringField("Category Name", validators=[DataRequired(), Length(min=2, max=100)])
    description = TextAreaField("Description", validators=[Optional(), Length(max=255)])
    submit = SubmitField("Save Category")


class SupplierForm(FlaskForm):
    name = StringField("Supplier / Vendor Name", validators=[DataRequired(), Length(min=2, max=120)])
    contact_person = StringField("Contact Person", validators=[Optional(), Length(max=100)])
    phone = StringField("Phone Number", validators=[Optional(), Length(max=50)])
    email = StringField("Email Address", validators=[Optional(), Email(), Length(max=120)])
    address = TextAreaField("Address", validators=[Optional(), Length(max=500)])
    submit = SubmitField("Save Supplier")


class ProductForm(FlaskForm):
    sku = StringField(
        "SKU / Barcode",
        validators=[
            DataRequired(),
            Length(min=2, max=50),
            Regexp(r"^[a-zA-Z0-9_-]+$", message="SKU can only contain letters, numbers, dashes, and underscores.")
        ]
    )
    name = StringField("Product Name", validators=[DataRequired(), Length(min=2, max=150)])
    description = TextAreaField("Description", validators=[Optional(), Length(max=1000)])
    category_id = SelectField("Category", coerce=int, validators=[DataRequired()])
    supplier_id = SelectField("Supplier", coerce=int, validators=[Optional()])
    unit_cost = DecimalField("Unit Cost ($)", places=2, validators=[DataRequired(), NumberRange(min=0.00)])
    selling_price = DecimalField("Selling Price ($)", places=2, validators=[DataRequired(), NumberRange(min=0.00)])
    reorder_level = IntegerField("Reorder Threshold", default=10, validators=[DataRequired(), NumberRange(min=0)])
    is_active = BooleanField("Active Product", default=True)
    submit = SubmitField("Save Product")


class StockInForm(FlaskForm):
    product_id = SelectField("Select Product", coerce=int, validators=[DataRequired()])
    quantity = IntegerField("Quantity Received", validators=[DataRequired(), NumberRange(min=1, message="Quantity must be at least 1 unit.")])
    unit_cost = DecimalField("Unit Cost (Optional update)", places=2, validators=[Optional(), NumberRange(min=0.00)])
    reference = StringField("PO / Invoice / Reference #", validators=[Optional(), Length(max=100)])
    notes = TextAreaField("Notes / Comments", validators=[Optional(), Length(max=500)])
    submit = SubmitField("Record Stock Receipt")


class StockOutForm(FlaskForm):
    product_id = SelectField("Select Product", coerce=int, validators=[DataRequired()])
    quantity = IntegerField("Quantity Issued / Sold", validators=[DataRequired(), NumberRange(min=1, message="Quantity must be at least 1 unit.")])
    reason = SelectField(
        "Issue Reason",
        choices=[
            ("Customer Sale", "Customer Sale / Dispatch"),
            ("Internal Usage", "Internal Usage / Department Issue"),
            ("Damaged / Expired", "Damaged / Expired / Scrap"),
            ("Transfer", "Warehouse Transfer"),
            ("Other", "Other")
        ],
        default="Customer Sale"
    )
    reference = StringField("Sales Order / Ticket / Slip #", validators=[Optional(), Length(max=100)])
    notes = TextAreaField("Notes / Comments", validators=[Optional(), Length(max=500)])
    submit = SubmitField("Record Stock Issue")


class StockAdjustmentForm(FlaskForm):
    product_id = SelectField("Select Product", coerce=int, validators=[DataRequired()])
    resulting_quantity = IntegerField("New Physical Count", validators=[DataRequired(), NumberRange(min=0, message="Physical count cannot be negative.")])
    reason = SelectField(
        "Adjustment Reason",
        choices=[
            ("Physical Audit Count", "Physical Audit Count Reconciliation"),
            ("Stock Discrepancy Found", "Stock Discrepancy Found"),
            ("Damaged Goods Written Off", "Damaged Goods Written Off"),
            ("Data Entry Correction", "Data Entry Correction"),
            ("Found Unrecorded Stock", "Found Unrecorded Stock")
        ],
        validators=[DataRequired()]
    )
    notes = TextAreaField("Audit Notes & Authorisation Details", validators=[DataRequired(), Length(min=5, max=500)])
    submit = SubmitField("Apply Stock Adjustment")
