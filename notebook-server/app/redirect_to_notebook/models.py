
from app.app import db
from datetime import datetime


class TokensManager(db.Model):
    __tablename__= 'tokens'
    token = db.Column(db.String, primary_key=True)
    used = db.Column(db.Boolean, default=False)

    def tokenExists(token):
        result = db.session.query(TokensManager.used).filter(TokensManager.token == token).first()
        return True if result != None and not result.used else False

    def addToken(token):
        new_token = TokensManager(token=token)
        db.session.add(new_token)
        db.session.commit()
        return True

    def markTokenUsed(token):
        token_row = TokensManager.query.filter_by(token=token).first()
        token_row.used = True
        db.session.commit()

class UsersContainers(db.Model):
    '''
    Model Class for Container Usage

    ORM mapping of container mapping user-container
    relationships. 

    SQL for corresponding table:

    CREATE TABLE UsersContainers(prolific_id VARCHAR(255) PRIMARY KEY, 
                                 container_id VARCHAR(255), 
                                 port INT,
                                 container_started_at DATETIME, 
                                 running  BOOL);
    '''

    __tablename__ = 'UsersContainers'
    prolific_id = db.Column(db.String, primary_key=True)
    container_id = db.Column(db.String)
    port = db.Column(db.Integer)
    container_started_at = db.Column(db.DateTime)
    running = db.Column(db.Boolean)

    def __repr__(self):
        return 'TODO: REPR FOR UsersContainers';
    
    def get_port(prolific_id):
        result =  db.session.query(UsersContainers.port).filter(UsersContainers.prolific_id == prolific_id).first().port
        return result

    def get_container_id(prolific_id):
        result =  db.session.query(UsersContainers.container_id).filter(UsersContainers.prolific_id == prolific_id).first().container_id
        return result

    def check_if_container_running(prolific_id):
        result =  db.session.query(UsersContainers.running).filter(UsersContainers.prolific_id == prolific_id).first().running
        return result

    def check_if_prolific_id_exists(prolific_id):
        return db.session.query(UsersContainers.prolific_id).filter_by(prolific_id=prolific_id).scalar() is not None
    
    def update_container_not_running(prolific_id):
        user = UsersContainers.query.filter_by(prolific_id=prolific_id).first()
        user.running = False
        db.session.commit()

    def handle_new_entry(prolific_id, container_id, port, running):
        '''Function that handles the logic of clicking on a patron type.'''
        new_user_container = UsersContainers(prolific_id=prolific_id, 
                                             container_id=container_id,
                                             port = port,
                                             container_started_at = datetime.now(),
                                             running = running)
        db.session.add(new_user_container)
        db.session.commit()
        return True

