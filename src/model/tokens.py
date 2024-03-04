from persistence.database import db
from model.user import User

class UserToken(db.Model):
    __tablename__ = 'UserToken'
    user_id = db.Column(db.Integer, db.ForeignKey(User.user_id, ondelete="CASCADE", onupdate="CASCADE"),
                        primary_key=False, nullable=False)
    token = db.Column(db.String(255), unique=True, nullable=False, primary_key=True)
    expiration = db.Column(db.DateTime, nullable=False)
    is_primary = db.Column(db.Boolean, nullable=False, default=False)