#!/usr/bin/env python3

import collections
import heapq
import tkinter
from math import *
from functools import reduce

Cube = collections.namedtuple("Cube", ["x", "y", "z"])
Point = collections.namedtuple("Point", ["x", "y"])
HexAxial = collections.namedtuple("HexAxial", ["q", "r"])
MapSize = collections.namedtuple("MapSize", ["x_1", "x_2", "y_1", "y_2"])


class Coord:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __repr__(self):
        return 'Coord x=%i y=%i' % (self.x, self.y)

    def __eq__(self, other):
        return self.x == other.x and self.y == other.y

    def __hash__(self):
        return hash((self.x, self.y))


class PriorityQueue:
    def __init__(self):
        self._queue = []
        self._index = 0

    def put(self, item, priority):
        heapq.heappush(self._queue, (priority, self._index, item))
        self._index += 1

    def get(self):
        return heapq.heappop(self._queue)[-1]

    def empty(self):
        return not self._queue


class HexTools:
    def __init__(self):
        self._cube_directions = [
            Cube(+1, -1, 0), Cube(+1, 0, -1), Cube(0, +1, -1),
            Cube(-1, +1, 0), Cube(-1, 0, +1), Cube(0, -1, +1),
        ]

    @staticmethod
    def _cube_to_offset(cube):
        col = cube.x + (cube.z - (cube.z & 1)) / 2
        row = cube.z
        return Coord(int(col), int(row))

    @staticmethod
    def _offset_to_cube(hex_):
        x = hex_.x - (hex_.y - (int(hex_.y) & 1)) / 2
        z = hex_.y
        y = -x - z
        return Cube(int(x), int(y), int(z))

    def distance(self, object_1, object_2):
        a = self._offset_to_cube(object_1)
        b = self._offset_to_cube(object_2)
        return int((abs(a.x - b.x) + abs(a.y - b.y) + abs(a.z - b.z)) / 2)

    @staticmethod
    def lerp(a, b, t):
        return a + (b - a) * t

    def cube_lerp(self, a, b, t):
        _a = self._offset_to_cube(a)
        _b = self._offset_to_cube(b)
        return Cube(self.lerp(_a.x, _b.x, t),
                    self.lerp(_a.y, _b.y, t),
                    self.lerp(_a.z, _b.z, t))

    @staticmethod
    def cube_round(cube):
        return Cube(round(cube.x), round(cube.y), round(cube.z))

    def line_draw(self, a, b):
        n = self.distance(a, b)
        results = set()
        for i in range(n + 1):
            results.add(self._cube_to_offset(self.cube_round(self.cube_lerp(a, b, 1.0 / n * i))))
        return results

    @staticmethod
    def cube_add(cube_1, cube_2):
        return Cube(x=cube_1.x + cube_2.x, y=cube_1.y + cube_2.y, z=cube_1.z + cube_2.z)

    def get_range(self, center, n):
        _center = self._offset_to_cube(center)
        results = set()
        for x in range(-n, n + 1):
            for y in range(max(-n, -x - n), min(+n, -x + n) + 1):
                z = -x - y
                results.add(self._cube_to_offset(self.cube_add(_center, Cube(x, y, z))))
        return results

    def cube_neighbor(self, cube, direction):
        return self.cube_add(cube, self._cube_directions[direction])

    def neighbor(self, offset, direction):
        cube = self._offset_to_cube(offset)
        return self._cube_to_offset(self.cube_add(cube, self._cube_directions[direction]))

    def hex_reachable(self, start, movement, blocked):
        visited = set()  # set of hexes
        _blocked = set([self._offset_to_cube(b) for b in blocked])
        _start = self._offset_to_cube(start)
        visited.add(_start)
        fringes = list()  # array of arrays of hexes
        fringes.append([_start])

        for k in range(1, movement + 1):
            fringes.append([])
            for cube in fringes[k - 1]:
                for d in range(6):
                    neighbor = self.cube_neighbor(cube, d)
                    if neighbor not in visited and neighbor not in _blocked:
                        visited.add(neighbor)
                        fringes[k].append(neighbor)

        return [self._cube_to_offset(v) for v in visited]

    @staticmethod
    def _checked_hex_the_same(hex_1, hex_2):
        return hex_1.x == hex_2.x and hex_1.y == hex_2.y

    def heuristic(self, a, b):
        # Manhattan distance on a square grid
        return self.distance(a, b)

    def best_way(self, start, goal, area=None):
        checked = list()
        frontier = PriorityQueue()
        frontier.put(start, 0)
        came_from = dict()
        came_from[start] = None
        current = start
        while not frontier.empty():
            current = frontier.get()
            checked.append(current)
            if current == goal:
                break
            for next_ in (self.neighbor(current, i) for i in range(6)):
                if area and next_ not in area:
                    continue
                if next_ not in came_from:
                    priority = self.heuristic(next_, goal)
                    came_from[next_] = current
                    frontier.put(next_, priority)
        if current != goal:
            return None
        path = []
        while current != start:
            path.append(current)
            current = came_from[current]
        path.reverse()
        return set(path)

    @staticmethod
    def oddr_offset_to_pixel(hex_, size):
        x = size * sqrt(3) * (hex_.x + 0.5 * (hex_.y & 1))
        y = size * 3 / 2 * hex_.y
        return Point(x, y)

    @staticmethod
    def axial_to_cube(hex_):
        x = hex_.q
        z = hex_.r
        y = -x - z
        return Cube(x, y, z)

    @staticmethod
    def pointy_hex_corner(center, size, i):
        angle_deg = 60 * i - 30
        angle_rad = pi / 180 * angle_deg
        return Point(center.x + size * cos(angle_rad),
                     center.y + size * sin(angle_rad))

    def hex_round(self, hex_):
        return self._cube_to_offset(self.cube_round(self.axial_to_cube(hex_)))

    def pixel_to_point_hex(self, point, size):
        q = (sqrt(3.) / 3. * point.x - 1. / 3. * point.y) / size
        r = (2. / 3. * point.y) / size
        return self.hex_round(HexAxial(q, r))

    def get_ring(self, offset, radius):
        checked = set()
        queue = set()
        queue.add(offset)
        for r in range(radius):
            new_queue = set()
            for el in queue:
                for i in range(6):
                    h = self.neighbor(el, i)
                    if h not in checked:
                        new_queue.add(h)
                        checked.add(h)
            queue = new_queue
        return queue


GRAY_COLORS = ['#e3e3e3', '#C7C7C7', '#4f4f4f']
BLUE_COLORS = ['#77bbd5', '#1D8FBA', '#0b394a', '#2bd4bf']
RED_COLORS = ['#ae8c8e', '#794044', '#30191b', '#e1434e']
RED_PLAYER = 0
BLUE_PLAYER = 1
RED_WIN = 1
BLUE_WIN = 2
SIZE = 20, 12
SCALE = 47
CANVAS_SIZE = SIZE[0] * SCALE, SIZE[1] * SCALE
HEX_SIZE = 25
OFFSET_TOP = 50
OFFSET_LEFT = 80
PLAYGROUND_SIZE = 11
PLAYGROUND_WITH_BOUNDARIES_SIZE = PLAYGROUND_SIZE + 2
TURN_HEX_POSITION = Coord(x=PLAYGROUND_SIZE + 7, y=0)
TURN_TEXT_POSITION = Coord(x=PLAYGROUND_SIZE + 5, y=0)
COMMENT_TEXT_POSITION = Coord(x=PLAYGROUND_SIZE + 6, y=2)
SIDE_HEX_POSITION = Coord(x=2, y=PLAYGROUND_SIZE + 1)
SIDE_TEXT_POSITION = Coord(x=0, y=PLAYGROUND_SIZE + 1)


class Game:
    def __init__(self):
        self.context = None
        self.master = tkinter.Tk()
        self.master.geometry("%ix%i" % CANVAS_SIZE)
        self.canvas = tkinter.Canvas(self.master, width=CANVAS_SIZE[0], height=CANVAS_SIZE[1])
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self.callback)

        self.hex_tools = HexTools()

        self.playground = set()
        self.boundary_blue_1 = set()
        self.boundary_blue_2 = set()
        self.boundary_red_1 = set()
        self.boundary_red_2 = set()
        self.boundary_corners = set()
        self.build_playground()

        self.list_of_blue = set()
        self.list_of_red = set()

        self.hints_blue = set()
        self.hints_red = set()

        self.refreshing_loop_time = 1000

        self._comment = None

    def auto_refresh(self):
        self.context.update()
        self.master.after(self.refreshing_loop_time, self.auto_refresh)

    @property
    def boundary_blue(self):
        return self.boundary_blue_1 | self.boundary_blue_2

    @property
    def boundary_red(self):
        return self.boundary_red_1 | self.boundary_red_2

    @property
    def boundary(self):
        return self.boundary_red | self.boundary_blue

    @property
    def active_area(self):
        v = self.playground - self.boundary_red - self.boundary_blue - self.boundary_corners
        return v - self.list_of_red - self.list_of_blue

    @property
    def all_red(self):
        return self.boundary_red | self.list_of_red

    @property
    def all_blue(self):
        return self.boundary_blue | self.list_of_blue

    def build_playground(self):
        for y in range(PLAYGROUND_WITH_BOUNDARIES_SIZE):
            for x in range(y // 2, y // 2 + PLAYGROUND_WITH_BOUNDARIES_SIZE):
                hex_xy = Coord(x, y)
                self.playground.add(hex_xy)
                if y == 0:
                    self.boundary_red_1.add(hex_xy)
                if y == PLAYGROUND_WITH_BOUNDARIES_SIZE - 1:
                    self.boundary_red_2.add(hex_xy)
                if x == y // 2:
                    self.boundary_blue_1.add(hex_xy)
                if x == y // 2 + PLAYGROUND_WITH_BOUNDARIES_SIZE - 1:
                    self.boundary_blue_2.add(hex_xy)

        self.boundary_corners = self.boundary_red & self.boundary_blue
        self.boundary_red_1 -= self.boundary_corners
        self.boundary_red_2 -= self.boundary_corners
        self.boundary_blue_1 -= self.boundary_corners
        self.boundary_blue_2 -= self.boundary_corners

    def draw_hex(self, _hex, fill):
        point = self.hex_tools.oddr_offset_to_pixel(_hex, HEX_SIZE)
        points = [self.hex_tools.pointy_hex_corner(point, HEX_SIZE, r) for r in range(6)]
        coord = reduce(lambda x, y: x + y, [[OFFSET_LEFT + p.x, OFFSET_TOP + p.y] for p in points])
        self.canvas.create_polygon(*coord, fill=fill, outline='black', width=1)

    def draw_text(self, _hex, text):
        point = self.hex_tools.oddr_offset_to_pixel(_hex, HEX_SIZE)
        return self.canvas.create_text(
            OFFSET_LEFT + point.x, OFFSET_TOP + point.y,
            fill="#373737", font="Calibri 20 bold",
            text=text
        )

    def draw_playground(self):
        for _hex in self.playground:
            fill = GRAY_COLORS[0]
            if _hex in self.boundary_blue:
                fill = BLUE_COLORS[2]
            if _hex in self.boundary_red:
                fill = RED_COLORS[2]
            if _hex in self.boundary_corners:
                fill = GRAY_COLORS[2]
            self.draw_hex(_hex, fill)
        self.clear_turn()

    def draw_turn(self, turn):
        self.draw_text(TURN_TEXT_POSITION, 'Next turn:')
        if turn:
            self.draw_hex(TURN_HEX_POSITION, BLUE_COLORS[1])
        else:
            self.draw_hex(TURN_HEX_POSITION, RED_COLORS[1])
        self.canvas.update()

    def draw_side(self, side):
        self.draw_text(SIDE_TEXT_POSITION, 'Your side:')
        if side:
            self.draw_hex(SIDE_HEX_POSITION, BLUE_COLORS[1])
        else:
            self.draw_hex(SIDE_HEX_POSITION, RED_COLORS[1])
        self.canvas.update()

    def draw_comment(self, comment):
        if self._comment is not None:
            self.canvas.delete(self._comment)
            self._comment = None

        self._comment = self.draw_text(COMMENT_TEXT_POSITION, comment)
        self.canvas.update()

    def clear_turn(self):
        self.draw_hex(TURN_HEX_POSITION, GRAY_COLORS[1])

    def callback(self, event):
        point = Point(event.x - OFFSET_LEFT, event.y - OFFSET_TOP)
        _hex = self.hex_tools.pixel_to_point_hex(point, HEX_SIZE)
        if _hex not in self.active_area:
            return
        else:
            if self.context is not None:
                self.context.click_hex(_hex)

    def add_hex(self, hex_coords, turn):
        if turn:
            self.list_of_blue.add(hex_coords)
            self.draw_hex(hex_coords, BLUE_COLORS[1])
        else:
            self.list_of_red.add(hex_coords)
            self.draw_hex(hex_coords, RED_COLORS[1])

    def draw_hints(self):
        finder = HintsFinder()

        hints = finder.find_all_hints(self.list_of_red, self.active_area)
        for h in hints:
            self.draw_hex(h, RED_COLORS[0])

        hints = finder.find_all_hints(self.list_of_blue, self.active_area)
        for h in hints:
            self.draw_hex(h, BLUE_COLORS[0])

    def check_result(self):
        one_red_boundary_1 = next(iter(self.boundary_red_1))
        one_red_boundary_2 = next(iter(self.boundary_red_2))

        way = self.hex_tools.best_way(one_red_boundary_1, one_red_boundary_2, area=self.all_red)
        if way:
            for h in way - self.boundary_red:
                self.draw_hex(h, fill=RED_COLORS[3])
            return RED_WIN

        one_blue_boundary_1 = next(iter(self.boundary_blue_1))
        one_blue_boundary_2 = next(iter(self.boundary_blue_2))

        way = self.hex_tools.best_way(one_blue_boundary_1, one_blue_boundary_2, area=self.all_blue)
        if way:
            for h in way - self.boundary_blue:
                self.draw_hex(h, fill=BLUE_COLORS[3])
            return BLUE_WIN

        return 0

    def bind_context(self, context):
        self.context = context

    def destroy(self):
        pass

    def run(self):
        self.draw_playground()
        self.auto_refresh()
        tkinter.mainloop()
        self.destroy()


class HintsFinder:
    def __init__(self):
        self.hex_tools = HexTools()

    def find_road_hints(self, list_, active_area):
        hints = list()
        for h_1 in list_:
            for h_2 in (self.hex_tools.get_ring(h_1, 2) & list_):
                between = (self.hex_tools.get_ring(h_1, 1) & self.hex_tools.get_ring(h_2, 1)) & active_area
                if len(between) == 2:
                    hints.append(between)
        return hints

    def find_all_hints(self, list_, active_area):
        hints_road = self.find_road_hints(list_, active_area)
        hints = set()
        for pair in hints_road:
            hints.update(pair)
        return hints


class SimpleController:
    def __init__(self, game_view, hints=False):
        self.result = 0
        self.turn = BLUE_PLAYER
        self.game_view = game_view
        self.game_view.draw_turn(self.turn)
        self.hints = hints
        self.started = False

    def click_hex(self, hex_object):
        if self.result:
            return

        self.game_view.add_hex(hex_object, self.turn)
        self.result = self.game_view.check_result()
        if self.result:
            if self.result == RED_WIN:
                print('Blue win!')
            else:
                print('Red win!')
            print('The end.')
        else:
            self.turn = not self.turn
            self.game_view.draw_turn(self.turn)

        if self.hints:
            self.game_view.draw_hints()

    def update(self):
        if not self.started:
            self.game_view.draw_turn(self.turn)
            print('Start')
            self.started = True

    def run_game(self):
        self.game_view.master.title('Game')
        self.game_view.run()


if __name__ == '__main__':
    game = Game()
    controller = SimpleController(game)
    game.bind_context(controller)
    controller.run_game()
