#!/usr/bin/env python


"""
Simple Chip-8 emulator written just for fun

@author: Nils Amiet

TODO: implement sound
TODO: implement controls
"""


from time import sleep
import os
import math
import curses
import random
import sys


class Instruction:
    """Abstract class representing an instruction"""
    def __init__(self, cpu):
        self.cpu = cpu

    def execute(self, opcode):
        pass


class OP0NNN(Instruction):
    """Calls RCA 1802 program at address NNN."""
    def execute(self, opcode):
        pass


class OP00E0(Instruction):
    """Clears the screen."""
    def execute(self, opcode):
        self.cpu.reset_screen()


class OP00EE(Instruction):
    """Returns from a subroutine."""
    def execute(self, opcode):
        self.cpu.program_counter = self.cpu.stack.pop()


class OP1NNN(Instruction):
    """Jumps to address NNN."""
    def execute(self, opcode):
        nnn = opcode & 0x0fff
        self.cpu.program_counter = nnn
        self.cpu.program_counter -= 2


class OP2NNN(Instruction):
    """Calls subroutine at NNN."""
    def execute(self, opcode):
        nnn = opcode & 0x0fff
        self.cpu.stack.append(self.cpu.program_counter)
        self.cpu.program_counter = nnn
        self.cpu.program_counter -= 2


class OP3XNN(Instruction):
    """Skips the next instruction if VX equals NN."""
    def execute(self, opcode):
        x = (opcode & 0x0f00) >> 8
        nn = opcode & 0x00ff
        vx = self.cpu.v_registers[x]

        if vx == nn:
            self.cpu.program_counter += 2


class OP4XNN(Instruction):
    """Skips the next instruction if VX doesn't equal NN."""
    def execute(self, opcode):
        x = (opcode & 0x0f00) >> 8
        nn = opcode & 0x00ff
        vx = self.cpu.v_registers[x]

        if vx != nn:
            self.cpu.program_counter += 2


class OP5XY0(Instruction):
    """Skips the next instruction if VX equals VY."""
    def execute(self, opcode):
        x = (opcode & 0x0f00) >> 8
        y = (opcode & 0x00f0) >> 4

        vx = self.cpu.v_registers[x]
        vy = self.cpu.v_registers[y]

        if vx == vy:
            self.cpu.program_counter += 2


class OP6XNN(Instruction):
    """Sets VX to NN."""
    def execute(self, opcode):
        x = (opcode & 0x0f00) >> 8
        nn = (opcode & 0x00ff)

        self.cpu.v_registers[x] = nn


class OP7XNN(Instruction):
    """Adds NN to VX."""
    def execute(self, opcode):
        x = (opcode & 0x0f00) >> 8
        nn = (opcode & 0x00ff)

        self.cpu.v_registers[x] += nn


class OP8XY0(Instruction):
    """Sets VX to the value of VY."""
    def execute(self, opcode):
        x = (opcode & 0x0f00) >> 8
        y = (opcode & 0x00f0) >> 4

        self.cpu.v_registers[x] = self.cpu.v_registers[y]


class OP8XY1(Instruction):
    """Sets VX to VX or VY."""
    def execute(self, opcode):
        x = (opcode & 0x0f00) >> 8
        y = (opcode & 0x00f0) >> 4

        vx = self.cpu.v_registers[x]
        vy = self.cpu.v_registers[y]

        self.cpu.v_registers[x] = vx | vy


class OP8XY2(Instruction):
    """Sets VX to VX and VY."""
    def execute(self, opcode):
        x = (opcode & 0x0f00) >> 8
        y = (opcode & 0x00f0) >> 4

        vx = self.cpu.v_registers[x]
        vy = self.cpu.v_registers[y]

        self.cpu.v_registers[x] = vx & vy


class OP8XY3(Instruction):
    """Sets VX to VX xor VY."""
    def execute(self, opcode):
        x = (opcode & 0x0f00) >> 8
        y = (opcode & 0x00f0) >> 4

        vx = self.cpu.v_registers[x]
        vy = self.cpu.v_registers[y]

        self.cpu.v_registers[x] = vx ^ vy


class OP8XY4(Instruction):
    """Adds VY to VX. VF is set to 1 when there's a carry,
    and to 0 when there isn't."""
    def execute(self, opcode):
        x = (opcode & 0x0f00) >> 8
        y = (opcode & 0x00f0) >> 4

        vx = self.cpu.v_registers[x]
        vy = self.cpu.v_registers[y]

        result = vx + vy
        carry = 1 if result > 0xff else 0

        self.cpu.v_registers[x] = result % 0xff
        self.cpu.v_registers[0xf] = carry


class OP8XY5(Instruction):
    """VY is subtracted from VX.
    VF is set to 0 when there's a borrow,
    and 1 when there isn't."""
    def execute(self, opcode):
        x = (opcode & 0x0f00) >> 8
        y = (opcode & 0x00f0) >> 4

        vx = self.cpu.v_registers[x]
        vy = self.cpu.v_registers[y]

        result = vx - vy

        if result < 0:
            borrow = 1
            result += 0xff
        else:
            borrow = 0

        self.cpu.v_registers[x] = result
        self.cpu.v_registers[0xf] = 1 - borrow


class OP8XY6(Instruction):
    """Shifts VX right by one.
    VF is set to the value of the
    least significant bit of VX before the shift."""
    def execute(self, opcode):
        x = (opcode & 0x0f00) >> 8
        y = (opcode & 0x00f0) >> 4

        vx = self.cpu.v_registers[x]
        lsb = vx & 1

        self.cpu.v_registers[0xf] = lsb
        self.cpu.v_registers[x] = vx >> 1


class OP8XY7(Instruction):
    """Sets VX to VY minus VX.
    VF is set to 0 when there's a borrow,
    and 1 when there isn't."""
    def execute(self, opcode):
        x = (opcode & 0x0f00) >> 8
        y = (opcode & 0x00f0) >> 4

        vx = self.cpu.v_registers[x]
        vy = self.cpu.v_registers[y]

        result = vy - vx

        if result < 0:
            borrow = 1
            result += 0xff
        else:
            borrow = 0

        self.cpu.v_registers[x] = result
        self.cpu.v_registers[0xf] = 1 - borrow


class OP8XYE(Instruction):
    """Shifts VX left by one.
    VF is set to the value of the
    most significant bit of VX before the shift."""
    def execute(self, opcode):
        x = (opcode & 0x0f00) >> 8
        y = (opcode & 0x00f0) >> 4

        vx = self.cpu.v_registers[x]
        msb = vx >> 7

        self.cpu.v_registers[0xf] = msb
        self.cpu.v_registers[x] = vx << 1


class OP9XY0(Instruction):
    """Skips the next instruction if VX doesn't equal VY."""
    def execute(self, opcode):
        x = (opcode & 0x0f00) >> 8
        y = (opcode & 0x00f0) >> 4

        vx = self.cpu.v_registers[x]
        vy = self.cpu.v_registers[y]

        if vx != vy:
            self.cpu.program_counter += 2


class OPANNN(Instruction):
    """Sets I to the address NNN."""
    def execute(self, opcode):
        nnn = opcode & 0x0fff
        self.cpu.i_register = nnn


class OPBNNN(Instruction):
    """Jumps to the address NNN plus V0."""
    def execute(self, opcode):
        nnn = opcode & 0x0fff
        v0 = self.cpu.v_registers[0]
        self.cpu.program_counter = nnn + v0
        self.cpu.program_counter -= 2


class OPCXNN(Instruction):
    """Sets VX to a random number and NN."""
    def execute(self, opcode):
        x = (opcode & 0x0f00) >> 8
        nn = opcode & 0x00ff

        rnd = random.randint(0, 255)
        self.cpu.v_registers[x] = rnd & nn


class OPDXYN(Instruction):
    """Sprites stored in memory at location in index register (I),
    maximum 8bits wide.
    Wraps around the screen.
    If when drawn, clears a pixel,
    register VF is set to 1 otherwise it is zero.
    All drawing is XOR drawing (e.g. it toggles the screen pixels)

    More info:
    Draw a sprite at position VX, VY with N bytes of sprite data starting at the address stored in I
    Set VF to 01 if any set pixels are changed to unset, and 00 otherwise
    """
    def execute(self, opcode):
        x = (opcode & 0x0f00) >> 8
        y = (opcode & 0x00f0) >> 4
        n = (opcode & 0x000f)

        vx = self.cpu.v_registers[x]
        vy = self.cpu.v_registers[y]
        i = self.cpu.i_register

        self.cpu.v_registers[0xf] = 0

        y_offset = 0
        for yc in range(vy, vy+n):
            sprite_row = self.cpu.memory[i + y_offset]
            y_offset += 1

            x_offset = 0
            for xc in range(vx, vx + 8):
                xc %= Chip8CPU.SCREEN_WIDTH
                yc %= Chip8CPU.SCREEN_HEIGHT
                # if xc >= Chip8CPU.SCREEN_WIDTH or yc >= Chip8CPU.SCREEN_HEIGHT:
                #     continue

                current_pixel = self.cpu.get_pixel(xc, yc)
                sprite_pixel = 0 if (sprite_row & (1 << (7 - x_offset))) == 0 else 1
                new_pixel = current_pixel ^ sprite_pixel
                x_offset += 1

                if current_pixel == 1 and sprite_pixel == 1:
                    self.cpu.v_registers[0xf] = 1

                self.cpu.set_pixel(xc, yc, new_pixel)


class OPEX9E(Instruction):
    """Skips the next instruction if the key stored in VX is pressed."""
    def execute(self, opcode):
        x = (opcode & 0x0f00) >> 8
        vx = self.cpu.v_registers[x]

        if self.cpu.inputs[vx] == 1:
            self.cpu.program_counter += 2


class OPEXA1(Instruction):
    """Skips the next instruction if the key stored in VX isn't pressed."""
    def execute(self, opcode):
        x = (opcode & 0x0f00) >> 8
        vx = self.cpu.v_registers[x]

        if self.cpu.inputs[vx] == 0:
            self.cpu.program_counter += 2


class OPFX07(Instruction):
    """Sets VX to the value of the delay timer."""
    def execute(self, opcode):
        x = (opcode & 0x0f00) >> 8
        self.cpu.v_registers[x] = self.cpu.delay_timer


class OPFX0A(Instruction):
    """A key press is awaited, and then stored in VX."""
    def execute(self, opcode):
        x = (opcode & 0x0f00) >> 8
        # TODO: unimplemented
        self.cpu.v_registers[x] = random.randint(0, 15)


class OPFX15(Instruction):
    """Sets the delay timer to VX."""
    def execute(self, opcode):
        x = (opcode & 0x0f00) >> 8
        vx = self.cpu.v_registers[x]
        self.delay_timer = vx


class OPFX18(Instruction):
    """Sets the sound timer to VX."""
    def execute(self, opcode):
        x = (opcode & 0x0f00) >> 8
        vx = self.cpu.v_registers[x]
        self.sound_timer = vx


class OPFX1E(Instruction):
    """Adds VX to I."""
    def execute(self, opcode):
        x = (opcode & 0x0f00) >> 8
        vx = self.cpu.v_registers[x]
        i = self.cpu.i_register

        result = i + vx
        self.cpu.v_registers[0xf] = 1 if result > 0xfff else 0
        self.cpu.i_register = result % 0xfff


class OPFX29(Instruction):
    """Sets I to the location of the sprite for the character in VX.
    Characters 0-F (in hexadecimal) are represented by a 4x5 font."""
    def execute(self, opcode):
        x = (opcode & 0x0f00) >> 8
        vx = self.cpu.v_registers[x]

        self.cpu.i_register = vx * 5


class OPFX33(Instruction):
    """Stores the Binary-coded decimal representation of VX,
    with the most significant of three digits at the address in I,
    the middle digit at I plus 1, and the least significant digit at I plus 2.
    (In other words, take the decimal representation of VX,
        place the hundreds digit in memory at location in I,
        the tens digit at location I+1, and the ones digit at location I+2.)"""
    def execute(self, opcode):
        x = (opcode & 0x0f00) >> 8
        vx = self.cpu.v_registers[x]

        hundreds = math.floor(vx / 100)
        vx -= hundreds * 100

        tens = math.floor(vx / 10)
        vx -= tens * 10

        units = vx

        i = self.cpu.i_register
        self.cpu.memory[i] = hundreds
        self.cpu.memory[i + 1] = tens
        self.cpu.memory[i + 2] = units


class OPFX55(Instruction):
    """Stores V0 to VX in memory starting at address I."""
    def execute(self, opcode):
        x = (opcode & 0x0f00) >> 8
        i = self.cpu.i_register
        self.cpu.memory[i:i + x + 1] = self.cpu.v_registers[0:x + 1]


class OPFX65(Instruction):
    """Fills V0 to VX with values from memory starting at address I."""
    def execute(self, opcode):
        x = (opcode & 0x0f00) >> 8
        i = self.cpu.i_register
        self.cpu.v_registers[0:x + 1] = self.cpu.memory[i:i + x + 1]


class Chip8CPU:
    "Chip-8 CPU"

    START_ADDRESS = 0x200
    SCREEN_WIDTH = 64
    SCREEN_HEIGHT = 32
    BLACK = 0
    WHITE = 1
    CHARS = {
        BLACK: ' ',
        WHITE: '\u2588'
        }

    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.reset_cpu()

        self.opcode_table = [
            # mask, expected result, instruction
            (0xf000, 0x0fff, OP0NNN(self)),
            (0xffff, 0x00e0, OP00E0(self)),
            (0xffff, 0x00ee, OP00EE(self)),
            (0xf000, 0x1000, OP1NNN(self)),
            (0xf000, 0x2000, OP2NNN(self)),
            (0xf000, 0x3000, OP3XNN(self)),
            (0xf000, 0x4000, OP4XNN(self)),
            (0xf00f, 0x5000, OP5XY0(self)),
            (0xf000, 0x6000, OP6XNN(self)),
            (0xf000, 0x7000, OP7XNN(self)),
            (0xf00f, 0x8000, OP8XY0(self)),
            (0xf00f, 0x8001, OP8XY1(self)),
            (0xf00f, 0x8002, OP8XY2(self)),
            (0xf00f, 0x8003, OP8XY3(self)),
            (0xf00f, 0x8004, OP8XY4(self)),
            (0xf00f, 0x8005, OP8XY5(self)),
            (0xf00f, 0x8006, OP8XY6(self)),
            (0xf00f, 0x8007, OP8XY7(self)),
            (0xf00f, 0x800e, OP8XYE(self)),
            (0xf00f, 0x9000, OP9XY0(self)),
            (0xf000, 0xa000, OPANNN(self)),
            (0xf000, 0xb000, OPBNNN(self)),
            (0xf000, 0xc000, OPCXNN(self)),
            (0xf000, 0xd000, OPDXYN(self)),
            (0xf0ff, 0xe09e, OPEX9E(self)),
            (0xf0ff, 0xe0a1, OPEXA1(self)),
            (0xf0ff, 0xf007, OPFX07(self)),
            (0xf0ff, 0xf00a, OPFX0A(self)),
            (0xf0ff, 0xf015, OPFX15(self)),
            (0xf0ff, 0xf018, OPFX18(self)),
            (0xf0ff, 0xf01e, OPFX1E(self)),
            (0xf0ff, 0xf029, OPFX29(self)),
            (0xf0ff, 0xf033, OPFX33(self)),
            (0xf0ff, 0xf055, OPFX55(self)),
            (0xf0ff, 0xf065, OPFX65(self))
        ]

    def reset_cpu(self):
        # memory
        self.memory = [0 for x in range(4096)]
        self.program_counter = Chip8CPU.START_ADDRESS
        self.stack = []

        # registers
        self.v_registers = [0 for x in range(16)]
        self.i_register = 0

        # timers
        self.delay_timer = 0
        self.sound_timer = 0

        # inputs
        self.inputs = [0 for x in range(16)]

        # graphics
        self.reset_screen()
        self.init_character_sprites()

    def init_character_sprites(self):
        # 0-F character sprites
        self.memory[0:80] = [
        0xf0, 0x90, 0x90, 0x90, 0xf0,
        0x20, 0x60, 0x20, 0x20, 0x70,
        0xf0, 0x10, 0xf0, 0x80, 0xf0,
        0xf0, 0x10, 0xf0, 0x10, 0xf0,
        0x90, 0x90, 0xf0, 0x10, 0x10,
        0xf0, 0x80, 0xf0, 0x10, 0xf0,
        0xf0, 0x80, 0xf0, 0x90, 0xf0,
        0xf0, 0x10, 0x20, 0x40, 0x40,
        0xf0, 0x90, 0xf0, 0x90, 0xf0,
        0xf0, 0x90, 0xf0, 0x10, 0xf0,
        0xf0, 0x90, 0xf0, 0x90, 0x90,
        0xe0, 0x90, 0xe0, 0x90, 0xe0,
        0xf0, 0x80, 0x80, 0x80, 0xf0,
        0xe0, 0x90, 0x90, 0x90, 0xe0,
        0xf0, 0x80, 0xf0, 0x80, 0xf0,
        0xf0, 0x80, 0xf0, 0x80, 0x80
        ]

    def reset_screen(self):
        self.screen = [
            [0 for x in range(Chip8CPU.SCREEN_WIDTH)]
            for y in range(Chip8CPU.SCREEN_HEIGHT)
        ]

    def update_timers(self):
        if self.delay_timer > 0:
            self.delay_timer -= 1

        if self.sound_timer > 0:
            self.sound_timer -= 1

    def print_debug(self):
        registers = ["V%s: %s" % (x, vx) for x, vx in enumerate(self.v_registers)]
        inputs = ["I%s: %s" % (i, ix) for i, ix in enumerate(self.inputs)]

        debug_line1 = "PC: %s | I: %s | DT: %s | ST: %s" % (self.program_counter, self.i_register, self.delay_timer, self.sound_timer)
        debug_line2 = " | ".join(registers)
        debug_line3 = " | ".join(inputs)

        self.stdscr.addstr(Chip8CPU.SCREEN_HEIGHT, 0, debug_line1)
        self.stdscr.addstr(Chip8CPU.SCREEN_HEIGHT + 1, 0, debug_line2)
        self.stdscr.addstr(Chip8CPU.SCREEN_HEIGHT + 2, 0, debug_line3)

    def print_screen(self):
        for i, row in enumerate(self.screen):
            text_row = [self.CHARS[pixel] for pixel in row]
            self.stdscr.addstr(i, 0, "".join(text_row))

    def set_pixel(self, x, y, value):
        self.screen[y][x] = value

    def get_pixel(self, x, y):
        return self.screen[y][x]

    def load_rom(self, rom_path):
        with open(rom_path, 'rb') as rom_file:
            i = Chip8CPU.START_ADDRESS

            byte = rom_file.read(1)
            while byte:
                self.memory[i] = byte[0]
                i += 1

                byte = rom_file.read(1)

    def fetch(self):
        """Fetches the next opcode from memory and returns it"""
        opcode = (self.memory[self.program_counter] << 8) + self.memory[self.program_counter + 1]
        return opcode

    def decode(self, opcode):
        """Decodes the opcode and returns the instruction to be executed"""
        for mask, result, instruction in self.opcode_table:
            if (opcode & mask) == result:
                return instruction

    def execute(self, instruction, opcode):
        """Executes instruction"""
        instruction.execute(opcode)

    def update_pc(self):
        self.program_counter += 2

    def cycle(self):
        opcode = self.fetch()
        instruction = self.decode(opcode)
        self.execute(instruction, opcode)
        self.update_pc()

    def start(self):
        """Runs the program"""
        while True:
            for i in range(4):
                self.cycle()

            self.stdscr.clear()
            self.print_debug()
            self.print_screen()
            self.stdscr.refresh()

            sleep(1/60)
            self.update_timers()


def main(stdscr, rom_path):
    cpu = Chip8CPU(stdscr)

    cpu.load_rom(rom_path)
    cpu.start()


if __name__ == "__main__":
    try:
        rom_path = sys.argv[1]
    except IndexError:
        print("usage: %s <rom_path>" % (sys.argv[0],))
        exit(1)

    try:
        stdscr = curses.initscr()
        curses.noecho()
        curses.cbreak()
        stdscr.keypad(True)
        curses.curs_set(0)

        main(stdscr, rom_path)

    finally:
        curses.nocbreak()
        stdscr.keypad(False)
        curses.echo()
        curses.endwin()
        curses.curs_set(1)
