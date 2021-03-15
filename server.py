#!/usr/bin/python3

# https://github.com/wwwtyro/gevent-websocket

import json,os
from flask import Flask, app, send_from_directory
from gevent import monkey; monkey.patch_all()
from werkzeug.debug import DebuggedApplication
from geventwebsocket import WebSocketServer, WebSocketApplication, Resource

flask_app = Flask(__name__)

flask_app._static_folder = os.path.abspath("static/")
flask_app.debug = True


class ChatApplication(WebSocketApplication):
    
    USERS = {}
    # {
    #     username: {
    #         "is_ready":False,
    #         "qi":0,
    #         "is_dead":False,
    #     }
    # }

    GAME = {
        'started': False
    }
    # {
    #     'started': False,
    #     'turn': 0,
    #     'turn_stats':{
    #         user1:{'action':1,'target':user2},
    #         user2:{},
    #         user3:{}
    #     }
    # }
    
    def on_open(self):
        print("Some client connected!")


    def on_message(self, message):
        if message is None:
            return

        print(message)
        data = json.loads(message)
        
        # gamer login
        if data["type"] == 'login' and self.GAME['started'] == False:
            self.USERS[data["content"]] = {'is_ready': False}
            if len(self.USERS) != 0:  # asyncio.wait doesn't accept an empty list
                message = json.dumps({
                    "type": "login",
                    "content": data["content"],
                    "user_list": list(self.USERS.keys())
                })
        
        # gamer logout
        elif data["type"] == 'logout':
            
            print("User logout.")
            print(len(self.USERS))
            print(data['content'])
            
            del self.USERS[data["content"]]
            
            self.GAME['started'] = False
            for _,sta in self.USERS.items():
                sta['is_ready'] = False
            
            if len(self.USERS) > 0:  # asyncio.wait doesn't accept an empty list
                message = json.dumps({
                    "type": "logout",
                    "content": data["content"],
                    "user_list": list(self.USERS.keys())
                })
                print(message)
        
        # gamer chat 
        elif data["type"] == 'send':
            message = json.dumps(
                {"type": "user", "content": data["content"], "from": data['from']})
        
        # gamer ready
        elif data["type"] == 'ready':
            # anti-cheat
            self.USERS[data['from']]['is_ready'] = True
            
            if len([1 for _,v in self.USERS.items() if v['is_ready']]) == len(self.USERS) and len(self.USERS) > 1:
                # if all gamer are ready, then start
                print("self.GAME start...")
                
                self.GAME['started'] = True
                self.GAME['turn'] = 1
                self.GAME['turn_stats'] = {}
                for u,_ in self.USERS.items():
                    self.USERS[u]['qi'] = 0
                    self.USERS[u]['is_dead'] = False
                
                # user's states
                print('uname\tqi\tis_ready\tis_dead')
                for k,v in self.USERS.items():
                    print(k + '\t' + str(v['qi']) + '\t' + str(v['is_ready']) + '\t' + str(v['is_dead']))
                
                message = json.dumps({"type": "system", "content": "All self.USERS ready, self.GAME start!"})
            else:
                # show user is ready
                message = json.dumps({"type": "ready", "user": data['from']})
        
        # gamer act
        # {
        #     'type':'act',
        #     'from':user1,
        #     'target':user2,
        #     'action':'y'
        # }
        elif data["type"] == 'act':
            
            if self.GAME['started'] == False:
                message = json.dumps({
                    "type":"system",
                    "content":"ERROR: self.GAME has not start"
                })
            elif 'target' in self.USERS.keys() and self.USERS[data['target']]['is_dead']:
                print('ERROR: target is already dead')
                message = json.dumps({
                    "type":"system",
                    "content":"ERROR: target is already dead"
                })
            
            else:
                self.GAME['turn_stats'][data['from']] = {
                    'action': data['action'],
                    'target': data['target'] if 'target' in data else ''
                }
                
                message = json.dumps({
                    "type": "system", 
                    "content": data['from'] + " has act in turn " + str(self.GAME['turn'])
                })
            
                # if everyone has act, then broadcast actions and results
                if len(self.GAME['turn_stats'].keys()) == len(self.USERS):
                    print('DEBUG: everyone has act')
                    
                    left = [u for u,sta in self.USERS.items() if not sta['is_dead']]
                    
                    for user,stats in self.GAME['turn_stats'].items():
                        
                        # check if under attack
                        b_from = []
                        db_from = []
                        x_from = []
                        y_from = []
                        for u,sta in self.GAME['turn_stats'].items():
                            if u == user:
                                continue
                            if sta['target'] == user and sta['action'] == 'b':
                                b_from.append(u)
                            if sta['target'] == user and sta['action'] == 'db':
                                db_from.append(u)
                            if sta['action'] == 'x':
                                x_from.append(u)
                            if sta['action'] == 'y':
                                y_from.append(u)
                                
                        print(json.dumps(b_from))
                        print(json.dumps(db_from))
                        print(json.dumps(x_from))
                        print(json.dumps(y_from))
                        
                        if stats['action'] in ['y','x'] and (len(b_from)>0 or len(db_from)>0):
                            print("hit rule 1")
                            self.USERS[user]['is_dead'] = True
                        
                        if stats['action'] == 'b':
                            if (len(b_from)>0 or len(db_from)>0) and not (len(db_from) == 0 and len(b_from) == 1 and b_from[0] == stats['target']):
                                print("hit rule 2")
                                self.USERS[user]['is_dead'] = True
                        
                        if stats['action'] == 'db':
                            if (len(b_from)>0 or len(db_from)>0) and not (len(b_from) == 0 and len(db_from) == 1 and db_from[0] == stats['target']):
                                print("hit rule 3")
                                self.USERS[user]['is_dead'] = True
                        
                        if stats['action'] == 'd' and len(db_from)>0:
                            print("hit rule 4")
                            self.USERS[user]['is_dead'] = True
                            
                        if stats['action'] == 'db' and self.USERS[user]['qi']<3:
                            print("hit rule 5")
                            self.USERS[user]['is_dead'] = True
                        
                        if stats['action'] == 'b' and self.USERS[user]['qi']<1:
                            print("hit rule 6")
                            self.USERS[user]['is_dead'] = True
                    
                        # check user's action
                        if stats['action'] == 'y' and len(x_from) == 0:
                            self.USERS[user]['qi'] += 1
                        
                        if stats['action'] == 'x' and len(y_from) > 0:
                            self.USERS[user]['qi'] += 1
                        
                        if stats['action'] == 'b':
                            self.USERS[user]['qi'] -= 1
                        
                        if stats['action'] == 'db':
                            self.USERS[user]['qi'] -= 3
                    
                    new_left = [u for u,sta in self.USERS.items() if not sta['is_dead']]
                    
                    # message summary
                    summary = json.dumps(self.GAME['turn_stats']) + ".\n"
                    summary += "Left self.USERS are: " + json.dumps(new_left) + "\n"
                    
                    # user's states
                    print('uname\tqi\tis_ready\tis_dead')
                    for k,v in self.USERS.items():
                        print(k + '\t' + str(v['qi']) + '\t' + str(v['is_ready']) + '\t' + str(v['is_dead']))
                    
                    if len(new_left) < len(left):
                        # if someone dead in this turn, all stats refresh
                        for u,_ in self.USERS.items():
                            self.USERS[u]['qi'] = 0
                    
                    self.GAME['turn_stats'] = {}    
                    
                    message = json.dumps({
                        "type": "system", 
                        "content": "Turn " + str(self.GAME['turn']) + " end. Summary: " + summary
                    })
                    self.GAME['turn'] += 1
                    
                    if len(new_left) <= 1:
                        # draw
                        if len(new_left) == 0:
                            message = json.dumps({"type":"system","content":"draw"})
                        if len(new_left) == 1:
                            # check if the self.GAME has a winner
                            message = json.dumps({"type":"system","content": "winner: "+new_left[0]})
                            
                        # clean self.GAME
                        self.GAME['started'] == False
                        for u,_ in self.USERS.items():
                            self.USERS[u]['is_ready'] = False
                pass
        
        # print("----------")
        # print(len(self.USERS))
        
        self.broadcast(message)

    def broadcast(self, message):
        for client in self.ws.handler.server.clients.values():
            client.ws.send(message)

    # def on_close(self, reason):
    #     print("Connection closed!")


@flask_app.route('/')
def index():
    return send_from_directory(os.path.abspath('static/'),'index.html')


WebSocketServer(
    None,
    Resource([
        ('^/chat', ChatApplication),
        ('^/.*', DebuggedApplication(flask_app))
    ]),
    debug=False
).serve_forever()
