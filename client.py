from game import Game, Coord
import socket
import selectors
import types
import server
import multiprocessing

BUFFER_SIZE = server.BUFFER_SIZE


class ClientController:
    def __init__(self, game_view, client_connection, hints=False):
        self.result = 0
        self.turn = True  # BLUE
        self.side = True  # BLUE
        self.game_view = game_view
        self.client_connection = client_connection
        self.hints = hints
        self._start = False
        self._connected = False
        self._opponent_exist = False
        self._receive_data = False

    def click_hex(self, hex_object):
        if self.result or not self._opponent_exist:
            return

        if self.turn == self.side:
            self.game_view.add_hex(hex_object, self.turn)
            self.result = self.game_view.check_result()
            self.client_connection.send_move(hex_object)
            if self.result:
                self._set_to_game_over()
            else:
                self._set_turn()

            if self.hints:
                self.game_view.draw_hints()

        self._get_opponent_move()

    def _set_to_game_over(self):
        if self.result == self.side + 1:
            self.game_view.draw_comment(u"You win! Well done.")
        else:
            self.game_view.draw_comment(u"Game over!")
        self.game_view.clear_turn()

    def _set_turn(self):
        self.turn = not self.turn
        self.game_view.draw_turn(self.turn)
        self.game_view.draw_comment(['Opponent move', 'Your move'][self.turn == self.side])

    def _get_opponent_move(self):
        move = self.client_connection.receive_move()
        if move:
            hex_object = Coord(x=move[0], y=move[1])
            self.game_view.add_hex(hex_object, not self.side)
            self.game_view.check_result()
            self._set_turn()

    def update(self):
        if self.result:
            return

        if not self._connected:
            self.game_view.draw_comment(u'Not connected')
            self._connected = self.connect()
        else:
            if not self._receive_data:
                self.side = self.client_connection.receive_side()
                self.game_view.draw_side(self.side)
                self.turn = self.client_connection.receive_turn()
                self._receive_data = True
            if self._receive_data and not self._start:
                self._opponent_exist = self.client_connection.check_opponent()
                if self._opponent_exist:
                    self.game_view.draw_turn(self.turn)
                    self._start = True

            if not self._start:
                self.game_view.draw_comment(u'Waiting.')
            else:
                self._opponent_exist = self.client_connection.check_opponent()
                if not self._opponent_exist:
                    self.game_view.draw_comment(u'Opponent has gone.')
                    self.game_view.clear_turn()
                    return
                self.game_view.draw_comment(['Opponent move', 'Your move'][self.turn == self.side])

        if self._start:
            if self.turn != self.side:
                self._get_opponent_move()

            self.result = self.game_view.check_result()
            if self.result:
                self._set_to_game_over()

    def run_game(self, number=None):
        if number:
            self.game_view.master.title('Player %i' % number)
        self.game_view.run()

    def connect(self):
        is_connected = self.client_connection.connect()
        return is_connected


class Client:
    def __init__(self, number):
        self.number = number
        self.socket = None
        self.selector = selectors.DefaultSelector()
        self.data = types.SimpleNamespace(
            side=None,
            turn=None,
            move=None,
            opponent=False
        )
        self.to_send = types.SimpleNamespace(
            move=None
        )

    def connect(self):
        server_address = (server.HOST, server.PORT)
        print('Client %i: starting %s' % (self.number, server_address))
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setblocking(False)
        self.socket.connect_ex(server_address)
        events = selectors.EVENT_READ | selectors.EVENT_WRITE
        self.selector.register(self.socket, events, data=None)
        return 1

    def service(self):
        try:
            events = self.selector.select(timeout=1)
            for key, mask in events:
                return self.service_connection(key, mask)
        except KeyboardInterrupt:
            print("caught keyboard interrupt, exiting")
            self.selector.close()

    def service_connection(self, key, mask):
        connection = key.fileobj

        if mask & selectors.EVENT_READ:
            status, command = server.receive(connection)
            if status:
                if command.head == 's':
                    self.data.side = command.values[1]
                    print('CLIENT %i: Receive side ' % self.number, self.data.side)
                if command.head == 't':
                    self.data.turn = command.values[1]
                    print('CLIENT %i: Receive turn ' % self.number, self.data.turn)
                if command.head == 'o':
                    self.data.opponent = command.values[1]
                    print('CLIENT %i: Receive opponent ' % self.number, self.data.opponent)
                if command.head == 'm':
                    self.data.move = command.values
                    print('CLIENT %i: Receive move ' % self.number, self.data.move)

        if mask & selectors.EVENT_WRITE:
            if self.to_send.move is not None:
                server.send(connection, 'm', self.to_send.move)
                print('CLIENT %i: Send move ' % self.number, self.to_send.move)
                self.to_send.move = None

    def receive_side(self):
        while self.data.side is None:
            self.service()
        return self.data.side

    def receive_turn(self):
        while self.data.turn is None:
            self.service()
        return self.data.turn

    def receive_move(self):
        self.service()
        if self.data.move is not None:
            m = self.data.move
            self.data.move = None
            return m
        else:
            return ()

    def check_opponent(self):
        self.service()
        return self.data.opponent

    def send_move(self, hex_coords):
        self.to_send.move = (hex_coords.x, hex_coords.y)
        while self.to_send.move is not None:
            self.service()


def run_new_client(number):
    game_view = Game()
    client_connection = Client(number)
    controller = ClientController(game_view, client_connection)
    game_view.bind_context(controller)
    controller.run_game(number)


if __name__ == '__main__':
    import sys

    number = int(sys.argv[1]) if sys.argv[1] else 0

    for n in range(number):
        c1 = multiprocessing.Process(target=run_new_client, args=(n+1, ))
        c1.start()
