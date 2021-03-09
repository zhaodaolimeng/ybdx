#!/usr/bin/env python
# WS server example that synchronizes state across clients

import asyncio
import json
import websockets


# arena start

USERS = {}
# {
#     username: {
#         "handler":ws, 
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

async def chat(websocket, path):
    
    await websocket.send(json.dumps({"type": "handshake"}))
    
    async for message in websocket:
        data = json.loads(message)
        print(data)
        # {'type': 'login', 'content': 'user75546270'}
        
        message = ''
        
        # gamer login
        if data["type"] == 'login' and GAME['started'] == False:
            USERS[data["content"]] = {'handler': websocket, 'is_ready': False}
            if len(USERS) != 0:  # asyncio.wait doesn't accept an empty list
                message = json.dumps({
                    "type": "login",
                    "content": data["content"],
                    "user_list": list(USERS.keys())
                })
        
        # gamer logout
        elif data["type"] == 'logout':
            
            print("User logout.")
            print(len(USERS))
            print(data['content'])
            
            del USERS[data["content"]]
            
            GAME['started'] = False
            for _,sta in USERS.items():
                sta['is_ready'] = False
            
            if len(USERS) > 0:  # asyncio.wait doesn't accept an empty list
                message = json.dumps({
                    "type": "logout",
                    "content": data["content"],
                    "user_list": list(USERS.keys())
                })
                print(message)
        
        # gamer chat 
        elif data["type"] == 'send':
           if USERS[data['from']]['handler'] == websocket:
               message = json.dumps(
                   {"type": "user", "content": data["content"], "from": data['from']})
        
        # gamer ready
        elif data["type"] == 'ready':
            # anti-cheat
            if USERS[data['from']]['handler'] == websocket:
                USERS[data['from']]['is_ready'] = True
            
            if len([1 for _,v in USERS.items() if v['is_ready']]) == len(USERS) and len(USERS) > 1:
                # if all gamer are ready, then start
                print("Game start...")
                
                GAME['started'] = True
                GAME['turn'] = 1
                GAME['turn_stats'] = {}
                for u,_ in USERS.items():
                    USERS[u]['qi'] = 0
                    USERS[u]['is_dead'] = False
                message = json.dumps({"type": "system", "content": "All users ready, game start!"})
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
            
            if GAME['started'] == False:
                print('ERROR: game has not start')
            elif USERS[data['from']]['handler'] != websocket:
                print('ERROR: username does not match the ws fingerprint')
            elif 'target' in USERS.keys() and USERS[data['target']]['is_dead']:
                print('ERROR: target is already dead')
            
            else:
                GAME['turn_stats'][data['from']] = {
                    'action': data['action'],
                    'target': data['target'] if 'target' in data else ''
                }
                
                message = json.dumps({
                    "type": "system", 
                    "content": data['from'] + " has act in turn " + GAME['turn']
                })
            
                # if everyone has act, then broadcast actions and results
                if len(GAME['turn_stats'].keys()) == len(USERS):
                    print('DEBUG: everyone has act')
                    
                    left = [u for u,sta in USERS.items() if not sta['is_dead']]
                    
                    for user,stats in GAME['turn_stats'].items():
                        
                        # check if under attack
                        b_from = []
                        db_from = []
                        x_from = []
                        y_from = []
                        for u,sta in GAME['turn_stats'].items():
                            if u == user:
                                continue
                            if sta['target'] == user and sta['action'] == 'b':
                                b_from += u
                            if sta['target'] == user and sta['action'] == 'db':
                                db_from += u
                            if sta['action'] == 'x':
                                x_from += u
                            if sta['action'] == 'y':
                                y_from += u
                        
                        if stats['action'] in ['y','x'] and (len(b_from)>0 or len(db_from)>0):
                            USERS[user]['is_dead'] = True
                        
                        if stats['action'] == 'b':
                            if not (len(db_from) == 0 and len(b_from) == 1 and b_from[0] == stats['target']):
                                USERS[user]['is_dead'] = True
                        
                        if stats['action'] == 'db':
                            if not (len(b_from) == 0 and len(db_from) == 1 and db_from[0] == stats['target']):
                                USERS[user]['is_dead'] = True
                        
                        if stats['action'] == 'd' and len(db_from)>0:
                            USERS[user]['is_dead'] = True
                            
                        if stats['action'] == 'db' and USERS[user]['qi']<3:
                            USERS[user]['is_dead'] = True
                        
                        if stats['action'] == 'b' and USERS[user]['qi']<1:
                            USERS[user]['is_dead'] = True
                    
                        # check user's action
                        if stats['action'] == 'y' and len(x_from) == 0:
                            USERS[user]['qi'] += 1
                        
                        if stats['action'] == 'x' and len(y_from) > 0:
                            USERS[user]['qi'] += 1
                        
                        if stats['action'] == 'b':
                            USERS[user]['qi'] -= 1
                        
                        if stats['action'] == 'db':
                            USERS[user]['qi'] -= 3
                    
                    # if someone dead in this turn, all stats refresh
                    new_left = [u for u,sta in USERS.items() if not sta['is_dead']]
                    
                    # message summary
                    summary = json.dumps(GAME['turn_stats']) + ".\n"
                    summary += "Left users are: " + json.dumps(new_left) + "\n"
                    
                    message = json.dumps({
                        "type": "system", 
                        "content": "Turn "+GAME['turn']+" end. Summary: " + summary
                    })
                    
                    if len(new_left) < len(left):
                        # check if the game has a winner
                        if len(new_left) ==  1:
                            message = json.dumps({"type":"gameend","winner":new_left[0]})
                            
                            # clean game
                            GAME['started'] == False
                            for u,_ in USERS.items():
                                USERS[u]['is_ready'] = False
                        else:   
                            GAME['turn'] += 1
                            GAME['turn_stats'] = {}
                    
                pass
        
        
        print("----------")
        print(len(USERS))
        
        # boardcast
        await asyncio.wait([user['handler'].send(message) for user in USERS.values()])


start_server = websockets.serve(chat, "127.0.0.1", 1234)

asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()
