#!/usr/bin/env python3
import socket
import selectors
import types

HOST = '127.0.0.1'
PORT = 65431
BUFFER_SIZE = 5


class GamesBase:
    games = list()
    _waiting_room = list()
    players_data = dict()
    _lost_players = list()

    def add_player(self):
        if not self._waiting_room:
            side = 0
            if not self.games:
                number = 1
            else:
                number = max([c for g in self.games for c in g]) + 1
            self._waiting_room.append(number)
        else:
            side = 1
            opponent_number = self._waiting_room.pop(0)
            number = opponent_number + 1
            self.games.append([opponent_number, number])

        self.players_data[number] = types.SimpleNamespace(
            side=side,
            turn=0,
            move=None
        )
        return number

    def remove_player(self, number):
        if number in self._waiting_room:
            self._waiting_room.remove(number)
            return
        if number in self._lost_players:
            self._lost_players.remove(number)
            return
        to_remove = [g for g in self.games if number in g]
        if to_remove:
            for r in to_remove:
                self._lost_players.append([i for i in r if i is not number][0])
                self.games.remove(r)

    def check_have_pair(self, number):
        if [p for p in self.games if number in p]:
            return 1
        else:
            return 0

    def check_player_exist(self, number):
        return number in self._waiting_room or number in self._lost_players

    def get_opponent(self, number):
        game = [g for g in self.games if number in g][0]
        return [c for c in game if c != number][0]


class Server:
    selector = selectors.DefaultSelector()
    games_base = GamesBase()

    def accept(self, sock):
        connection, address = sock.accept()
        print('Server: accept ', address)
        connection.setblocking(False)

        player_number = self.games_base.add_player()

        events = selectors.EVENT_READ | selectors.EVENT_WRITE
        data = types.SimpleNamespace(
            player_number=player_number,
            opponent_exist=False,
            side_sent=False,
            turn_sent=False,
        )
        self.selector.register(connection, events, data)

    def service_connection(self, key, mask):
        connection, data = key.fileobj, key.data
        player_data = self.games_base.players_data[data.player_number]

        if mask & selectors.EVENT_READ:
            status, command = receive(connection)
            print(status)
            print(command)

            if status and command.head == 'm':
                player_data.move = command.values
                print('SERVER" receive move ', command.values, ' from ', data.player_number)
            else:
                print('SERVER: closing', data.player_number)

                self.games_base.remove_player(data.player_number)
                self.selector.unregister(connection)
                connection.close()
                return

        if mask & selectors.EVENT_WRITE:
            if not data.side_sent:
                send(connection, 's', (player_data.side,))
                data.side_sent = True
                print('SERVER: send side ', player_data.side, ' to ', data.player_number)

            elif not data.turn_sent:
                send(connection, 't', (player_data.turn,))
                data.turn_sent = True
                print('SERVER: send turn ', player_data.turn, ' to ', data.player_number)

            elif data.opponent_exist and not self.games_base.check_have_pair(data.player_number):
                send(connection, 'o', (0,))
                data.opponent_exist = False
                print('SERVER: send opponent not exist for ', data.player_number)

            elif not data.opponent_exist and self.games_base.check_have_pair(data.player_number):
                send(connection, 'o', (1,))
                data.opponent_exist = True
                print('SERVER: send opponent exist for ', data.player_number)

            else:
                have_opponent = self.games_base.check_have_pair(data.player_number)
                if have_opponent:
                    opponent_number = self.games_base.get_opponent(data.player_number)
                    opponent_data = self.games_base.players_data[opponent_number]
                    if opponent_data.move:
                        send(connection, 'm', opponent_data.move)
                        print('SERVER: send move', opponent_data.move, ' to ', data.player_number)
                        opponent_data.move = None

    def run(self):
        host, port = HOST, PORT
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind((host, port))
        s.listen()
        print('SERVER: listen')
        s.setblocking(False)
        self.selector.register(s, selectors.EVENT_READ, data=None)

        try:
            while True:
                events = self.selector.select(timeout=None)
                for key, mask in events:
                    if key.data is None:
                        self.accept(key.fileobj)
                    else:
                        self.service_connection(key, mask)
        except KeyboardInterrupt:
            print("CLIENT: caught keyboard interrupt, exiting")
        finally:
            self.selector.close()


def receive(connection):
    recv_head = connection.recv(1)
    if recv_head:
        recv_data = connection.recv(4)
        Command = types.SimpleNamespace(head=recv_head.decode('utf-8'),
                                        values=(int(recv_data[:2]), int(recv_data[2:])))
        return True, Command
    else:
        return False, None


def send(connection, head, values):
    if len(values) == 1:
        command_values = 0, values[0]
    elif len(values) == 2:
        command_values = values[0], values[1]
    else:
        raise ValueError
    command = head + ('%02i' % command_values[0]) + ('%02i' % command_values[1])
    bytes_command = command.encode('utf-8')
    connection.send(bytes_command)


if __name__ == '__main__':
    server = Server()
    server.run()
