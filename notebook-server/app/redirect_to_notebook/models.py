from app.app import db
from datetime import datetime

#List of patron types in the enumerated 'patron_types'
#field in the MySQL database
PATRON_TYPES = [
'CMA Staff',
'CWRU Joint Program',
'Museum Member',
'Public',
]

class PatronCount(db.Model):
    '''
    Object Relational mapping of database made in
    create_library_checkin_db.sql.
    '''

    __tablename__ = 'patron_counts'
    id = db.Column(db.Integer, primary_key=True)
    checkin_time = db.Column(db.DateTime)
    patron_type = db.Column(db.String)

    def __repr__(self):
        return '<Time %r>' % (self.time)
    
    def handle_checkin_click(patron_type, PATRON_TYPES):
        '''Function that handles the logic of clicking on a patron type.'''
        try:
            print("PATRON TYPE: %s"%(patron_type))
            new_count = PatronCount(checkin_time=datetime.now(), patron_type=patron_type)
            db.session.add(new_count)
            db.session.commit()
            return True
        except Exception:
            print('Something Went Wrong')
            return False
