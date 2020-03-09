import datetime
import os
import struct
import sys
import time
from tkinter import *

import matplotlib.animation as animation
import matplotlib.style
import serial
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

import visa
import queue as Queue
import threading

import statistics

if sys.version_info[0] < 3:
    import Tkinter as tk
else:
    import tkinter as tk

matplotlib.style.use('ggplot')

SMU_ID = 'USB0::0x0957::0x8B18::MY51141538::0::INSTR'
DEFAULT_COM_PORT = "COM5"

# In this experint is used only to measure voltage
DEFAULT_ANALOG_2_RES = "999999"


# matplotlib.use("TkAgg")

class STMprotocol:
    def __init__(self, serial_port):
        self.ser = serial.Serial(serial_port, 250000, timeout=0.2)
        self.pack_format = {
            0x01: "=BBBB",
            0x02: "=B",
            0x03: "=B",
            0x04: "=f",
            0x05: "=f"
        }

        self.unpack_format = {
            0x01: "=BBBB",
            0x02: "=f",
            0x03: "=f",
            0x04: "=BB",
            0x05: "=BB"
        }

    def send_command(self, cmd, args):
        # Clear buffer
        # print(self.ser.read(self.ser.in_waiting))

        parameters = bytearray(struct.pack(self.pack_format[cmd], *args))
        # print(parameters)
        msg_len = len(parameters) + 5
        msg = bytearray([0xfa, 0xaf, msg_len, cmd]) + parameters
        crc = sum(msg) % 256
        msg += bytearray([crc])

        # print("send ", repr(msg))
        self.ser.write(msg)

        start_time = datetime.datetime.now()
        time_threshold = datetime.timedelta(seconds=1)
        dt = start_time - start_time

        time.sleep(0.001)
        data = self.ser.read()[0]
        while (data != 0xfa) and (dt < time_threshold):
            data = self.ser.read()[0]

            current_time = datetime.datetime.now()
            dt = start_time - current_time

        adr = self.ser.read()[0]
        answer_len = self.ser.read()[0]
        answer = bytearray(self.ser.read(answer_len - 3))
        # print("answer ", repr(bytearray([data, adr, answer_len]) + answer))

        args = struct.unpack(self.unpack_format[cmd], answer[1:-1])
        return args

class SmuThreadedTask(threading.Thread):
    def __init__(self, queue):
        threading.Thread.__init__(self)
        self.queue = queue

        # Set up smu
        self.rm = visa.ResourceManager()
        self.smu = self.rm.open_resource(SMU_ID)
        self.smu_volt = 0
        self.smu_curr = 0
        self.pause = True
        self.setup_smu()


    def setup_smu(self):
        # Full setup
        print("SMU setup...")

        print("Reset smu: ", self.smu.write("*RST"))
        print("Clear status byte reg: ", self.smu.write("*CLS"))


        print("Set source output shape: ", self.smu.write("SOUR1:FUNC DC"))
        print("Get source output shape: ", self.smu.query("SOUR1:FUNC?"))

        print("Set source output mode: ", self.smu.write("SOUR1:FUNC:MODE VOLT"))
        print("Get source output mode: ", self.smu.query("SOUR1:FUNC:MODE?"))

        print("Set voltage range: ", self.smu.write("SOUR1:VOLT:RANG 20"))
        print("Get voltage range: ", self.smu.query("SOUR1:VOLT:RANG?"))

        print("Set current range: ", self.smu.write("SENS1:CURR:RANGE 0.001"))
        print("Get current range: ", self.smu.query("SENS1:CURR:RANGE?"))

        print("Set current limit: ", self.smu.write("SENS1:CURR:PROT 0.001"))
        print("Get current limit: ", self.smu.query("SENS1:CURR:PROT?"))

        print("Set integration time V: ", self.smu.write("SENS1:VOLT:APER 1"))
        print("Get integration time V: ", self.smu.query("SENS1:VOLT:APER?"))

        print("Set integration time I: ", self.smu.write("SENS1:CURR:APER 1"))
        print("Get integration time I: ", self.smu.query("SENS1:CURR:APER?"))

        print("Source voltage...")

        print("Set sourced voltage: ", self.smu.write("SOUR1:VOLT 4.05"))
        # print("Set sourced voltage: ", self.smu.write("SOUR1:VOLT 3.7"))
        print("Get sourced voltage: ", self.smu.query("SOUR1:VOLT?"))

        print("Enable output...")
        print("Set output on: ", self.smu.write("OUTPUT1 ON"))
        print("Is output on?: ", self.smu.query("OUTPUT1?"))

    def pause_smu(self):
        self.pause = True

    def resume_smu(self):
        self.pause = False

    def smu_measure(self):
        self.smu_volt = float(self.smu.query("MEAS:VOLT? (@1)")[:-1])
        self.smu_curr = float(self.smu.query("MEAS:CURR? (@1)")[:-1])

    def close_smu(self):
        self.smu.close()
        print("SMU closed.")

    def run(self):
        while True:
            if self.pause is False:
                # Measure I and V
                self.smu_measure()
                # Put data ina queue
                self.queue.put([self.smu_volt, self.smu_curr])
            else:
                time.sleep(0.1)


class App:
    def __init__(self, master):
        self.master = master

        # File name for data and final data
        self.data_file_name = 'data_' + datetime.datetime.now().strftime('%d_%m_%Y_%H_%M') + '.txt'

        # Align rows and columns of master
        Grid.rowconfigure(master, 0, weight=1)
        Grid.rowconfigure(master, 1, weight=1)
        Grid.columnconfigure(master, 0, weight=1)
        Grid.columnconfigure(master, 1, weight=1)
        Grid.columnconfigure(master, 2, weight=1)
        Grid.columnconfigure(master, 3, weight=1)
        Grid.columnconfigure(master, 4, weight=1)
        Grid.columnconfigure(master, 5, weight=1)
        Grid.columnconfigure(master, 6, weight=1)

        # Create bottom frame for buttons, labels and entry windows
        self.bottom_frame = Frame(self.master, background="white")
        self.bottom_frame.grid(row=1, column=0, columnspan=6, sticky=N + S + E + W)

        # Configure sub grid
        Grid.columnconfigure(self.bottom_frame, 0, weight=1)
        Grid.columnconfigure(self.bottom_frame, 1, weight=1)
        Grid.columnconfigure(self.bottom_frame, 2, weight=1)
        Grid.columnconfigure(self.bottom_frame, 3, weight=1)
        Grid.columnconfigure(self.bottom_frame, 4, weight=1)
        Grid.columnconfigure(self.bottom_frame, 5, weight=1)
        Grid.rowconfigure(self.bottom_frame, 0, weight=1)
        Grid.rowconfigure(self.bottom_frame, 1, weight=1)
        Grid.rowconfigure(self.bottom_frame, 2, weight=1)
        Grid.rowconfigure(self.bottom_frame, 3, weight=1)

        # Create labels (names)
        label_1 = Label(self.bottom_frame, text="Temperature 1, C", fg="black", bg="white")
        label_2 = Label(self.bottom_frame, text="Temperature 2, C", fg="black", bg="white")
        label_3 = Label(self.bottom_frame, text="Temperature 3, C", fg="black", bg="white")
        label_4 = Label(self.bottom_frame, text="Voltage diff. 1, mv", fg="black", bg="white")
        label_5 = Label(self.bottom_frame, text="Voltage diff. 2, mv", fg="black", bg="white")
        label_6 = Label(self.bottom_frame, text="COM port", fg="black", bg="white")
        label_7 = Label(self.bottom_frame, text="Resistance 1, ohm", fg="black", bg="white")
        label_8 = Label(self.bottom_frame, text="Resistance 2, ohm", fg="black", bg="white")
        label_9 = Label(self.bottom_frame, text="Target temp. 1, C", fg="black", bg="white")
        label_10 = Label(self.bottom_frame, text="Target temp. 3, C", fg="black", bg="white")
        # Place labels with grid method
        label_1.grid(row=0, column=0, sticky=N + S + E + W)
        label_2.grid(row=0, column=1, sticky=N + S + E + W)
        label_3.grid(row=0, column=2, sticky=N + S + E + W)
        label_4.grid(row=0, column=3, sticky=N + S + E + W)
        label_5.grid(row=0, column=4, sticky=N + S + E + W)
        label_6.grid(row=0, column=5, sticky=N + S + E + W)
        label_7.grid(row=2, column=3, sticky=N + S + E + W)
        label_8.grid(row=2, column=4, sticky=N + S + E + W)
        label_9.grid(row=2, column=0, sticky=N + S + E + W)
        label_10.grid(row=2, column=1, sticky=N + S + E + W)
        # Config the fonts
        updating_label_font_size = 14
        updating_label_font_type = 'Arial'
        # Config the fonts
        label_1.config(font=(updating_label_font_type, updating_label_font_size))
        label_2.config(font=(updating_label_font_type, updating_label_font_size))
        label_3.config(font=(updating_label_font_type, updating_label_font_size))
        label_4.config(font=(updating_label_font_type, updating_label_font_size))
        label_5.config(font=(updating_label_font_type, updating_label_font_size))
        label_6.config(font=(updating_label_font_type, updating_label_font_size))
        label_7.config(font=(updating_label_font_type, updating_label_font_size))
        label_8.config(font=(updating_label_font_type, updating_label_font_size))
        label_9.config(font=(updating_label_font_type, updating_label_font_size))
        label_10.config(font=(updating_label_font_type, updating_label_font_size))

        # Create changing labels
        self.label_temp_1 = Label(self.bottom_frame, text="10", fg="black", bg="white")
        self.label_temp_2 = Label(self.bottom_frame, text="11", fg="black", bg="white")
        self.label_temp_3 = Label(self.bottom_frame, text="12", fg="black", bg="white")
        self.label_volt_1 = Label(self.bottom_frame, text="13", fg="black", bg="white")
        self.label_volt_2 = Label(self.bottom_frame, text="14", fg="black", bg="white")
        self.entry_COM = Entry(self.bottom_frame, fg="black", bg="white", justify='center')
        self.entry_res_1 = Entry(self.bottom_frame, fg="black", bg="white", justify='center')
        self.entry_res_2 = Entry(self.bottom_frame, fg="black", bg="white", justify='center')
        self.entry_temp_1 = Entry(self.bottom_frame, fg="black", bg="white", justify='center')
        self.entry_temp_2 = Entry(self.bottom_frame, fg="black", bg="white", justify='center')
        # Config the fonts
        self.label_temp_1.config(font=(updating_label_font_type, updating_label_font_size), fg="blue")
        self.label_temp_2.config(font=(updating_label_font_type, updating_label_font_size), fg="green")
        self.label_temp_3.config(font=(updating_label_font_type, updating_label_font_size), fg="red")
        self.label_volt_1.config(font=(updating_label_font_type, updating_label_font_size), fg="purple")
        self.label_volt_2.config(font=(updating_label_font_type, updating_label_font_size), fg="brown")
        self.entry_COM.config(font=(updating_label_font_type, updating_label_font_size))
        self.entry_res_1.config(font=(updating_label_font_type, updating_label_font_size), fg="purple")
        self.entry_res_2.config(font=(updating_label_font_type, updating_label_font_size), fg="brown")
        self.entry_temp_1.config(font=(updating_label_font_type, updating_label_font_size), fg="blue")
        self.entry_temp_2.config(font=(updating_label_font_type, updating_label_font_size), fg="red")
        # Place labels with grid method
        self.label_temp_1.grid(row=1, column=0, sticky=N + S + E + W)
        self.label_temp_2.grid(row=1, column=1, sticky=N + S + E + W)
        self.label_temp_3.grid(row=1, column=2, sticky=N + S + E + W)
        self.label_volt_1.grid(row=1, column=3, sticky=N + S + E + W)
        self.label_volt_2.grid(row=1, column=4, sticky=N + S + E + W)
        self.entry_COM.grid(row=1, column=5)
        self.entry_res_1.grid(row=3, column=3)
        self.entry_res_2.grid(row=3, column=4)
        self.entry_temp_1.grid(row=3, column=0)
        self.entry_temp_2.grid(row=3, column=1)

        # Create checkButton
        self.exp_flag = IntVar()
        self.exp_check_button = Checkbutton(self.bottom_frame, text='Experiment mode', variable=self.exp_flag,
                                            fg="black", bg="white", )
        self.exp_check_button.grid(row=3, column=2)
        self.exp_check_button.config(font=(updating_label_font_type, updating_label_font_size))

        # Create Start-stop button
        self.button_start_stop = Button(self.bottom_frame, text="Start", fg="black", bg="white")
        # Place it
        self.button_start_stop.grid(row=2, column=5)
        # Configure font
        self.button_start_stop.config(font=(updating_label_font_type, updating_label_font_size))
        # Bind a callback
        self.button_start_stop.bind("<Button-1>", self.button_start_stop_callback)

        # Create Clear data button
        self.button_clear_data = Button(self.bottom_frame, text="Clear data", fg="black", bg="white")
        # Place it
        self.button_clear_data.grid(row=3, column=5)
        # Configure font
        self.button_clear_data.config(font=(updating_label_font_type, updating_label_font_size))
        # Bind a callback
        self.button_clear_data.bind("<Button-1>", self.button_clear_data_callback)

        # Create Update params button
        self.button_update_params = Button(self.bottom_frame, text="Update", fg="black", bg="white")
        # Place it
        self.button_update_params.grid(row=2, column=2)
        # Configure font
        self.button_update_params.config(font=(updating_label_font_type, updating_label_font_size))
        # Bind a callback
        self.button_update_params.bind("<Button-1>", self.update_button_callback)

        # Settings for a figure
        self.font_title_size = 16

        # Create a figure
        self.figure_1 = Figure(figsize=(16, 5), dpi=100)
        self.axes_1 = self.figure_1.add_subplot(131)
        self.axes_2 = self.figure_1.add_subplot(132)
        self.axes_3 = self.figure_1.add_subplot(133)
        self.axes_3_twin = self.axes_3.twinx()

        # Create containers for graphs
        self.graph_container_1 = Frame(self.master)

        # Allocate containers via grid method
        self.graph_container_1.grid(row=0, column=0, columnspan=6)

        # Create canvas
        self.canvas_graph_1 = FigureCanvasTkAgg(self.figure_1, self.graph_container_1)
        self.canvas_graph_1.draw()

        # Create widget
        self.graph_1_widget = self.canvas_graph_1.get_tk_widget()
        self.graph_1_widget.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)

        # Open COM
        # try:
        #     self.protocol = STMprotocol('COM5')
        # except ValueError:
        #     print("COM error")

        # Initial values for resistanses and temperatures
        self.res_1_value = 0
        self.res_2_value = 0
        self.entry_COM.insert(0, DEFAULT_COM_PORT)
        self.entry_res_1.insert(0, "0.0")
        self.entry_res_2.insert(0, DEFAULT_ANALOG_2_RES)

        self.target_temp_cold = 25
        self.target_temp_hot = 25
        self.entry_temp_1.insert(0, "25.0")
        self.entry_temp_2.insert(0, "25.0")

        # Animation
        self.ani = animation.FuncAnimation(self.figure_1, self.animate, interval=2000)

        # Pause
        self.pause = True

        self.params_tem = {'alpha': 0.0004 * 36,
                           'r_tem': 2 * 1.53,
                           'T': 300,
                           'R_tem': 54.06 / 2}

        self.voltage_prediction = [0, 0]

        # Create objects for SMU support
        self.queue = Queue.Queue()
        self.smu_thread = SmuThreadedTask(self.queue)
        self.smu_thread.start()
        self.smu_msg = [0, 0]

    def process_data_from_smu(self):
        try:
            self.smu_msg = self.queue.get(0)
            # Show result of the task if needed
            print("Data from SMU")

        except Queue.Empty:
            print("No new data from SMU")

    def calc_therm_res(self, R_tem, alpha, T, r_load, r_tem):
        R = R_tem / (1 + R_tem * alpha ** 2 * T / (r_load + r_tem)) + 1
        return R

    def calc_theoretical_voltages(self):
        answer = []
        try:
            temp_cold = float(self.entry_temp_1.get())
            temp_hot = float(self.entry_temp_2.get())
        except:
            temp_cold = 0
            temp_hot = 0
        dtemp = temp_hot - temp_cold
        therm_res_1 = self.calc_therm_res(r_load=self.res_1_value, **self.params_tem)
        therm_res_2 = self.calc_therm_res(r_load=self.res_2_value, **self.params_tem)
        q = dtemp / (therm_res_1 + therm_res_2)
        answer.append(q * therm_res_1 * self.params_tem['alpha'] * self.res_1_value /
                      (self.res_1_value + self.params_tem['r_tem']) * 1000)
        answer.append(q * therm_res_2 * self.params_tem['alpha'] * self.res_2_value /
                      (self.res_2_value + self.params_tem['r_tem']) * 1000)
        return answer

    def animate(self, arg2):
        if self.pause is False:
            # Look for the data from SMU
            self.process_data_from_smu()
            # Get data from Control board
            self.get_data(self)

            # Check that file exists
            if not os.path.exists(self.data_file_name):
            	print("There is no file with data.")
            	return

            file = open(self.data_file_name, 'r')

            n = 60 * 10
            pull_data = self.tail(file, n)
            data_array = pull_data[0]
            time_val = []
            temp_1_val = []
            temp_2_val = []
            temp_3_val = []
            volt_1_val = []
            volt_2_val = []
            smu_volt_val = []
            smu_curr_val = []
            for eachLine in data_array:
                if len(eachLine) > 1:
                    time, temp_1, temp_2, temp_3, volt_1, volt_2, res_1, res_2, smu_volt, smu_curr = eachLine.split(',')
                    time_val.append(datetime.datetime.strptime(time, '%d.%m.%Y %H:%M:%S'))
                    temp_1_val.append(float(temp_1))
                    temp_2_val.append(float(temp_2))
                    temp_3_val.append(float(temp_3))
                    volt_1_val.append(float(volt_1))
                    volt_2_val.append(float(volt_2))
                    smu_volt_val.append(float(smu_volt))
                    smu_curr_val.append(float(smu_curr))

            # Convert from V to mV
            volt_1_val = [x * 1000 for x in volt_1_val]
            volt_2_val = [x * 1000 for x in volt_2_val]
            # Convert from A to mA
            smu_curr_val = [x * 1000 for x in smu_curr_val]

            # Plot temperatures
            self.axes_1.clear()
            self.axes_1.plot(time_val, temp_1_val, color="blue")
            self.axes_1.plot(time_val, temp_2_val, color="green")
            self.axes_1.plot(time_val, temp_3_val, color="red")
            self.axes_1.set_title("Temperatures, C", fontsize=self.font_title_size)

            # Plot voltages
            self.axes_2.clear()
            self.axes_2.plot(time_val, volt_1_val, color="purple")
            self.axes_2.plot(time_val, volt_2_val, color="brown")
            self.axes_2.set_title("Voltages, mV", fontsize=self.font_title_size)

            # Plot smu current
            self.axes_3.clear()
            self.axes_3_twin.clear()
            self.axes_3.plot(time_val, smu_curr_val, color="red")
            # Plot smu voltage
            self.axes_3_twin.plot(time_val, smu_volt_val, color="blue")
            # Add horizontal lines to plot average current
            self.axes_3.axhline(statistics.mean(smu_curr_val), linestyle='--', color="red")
            self.axes_3.set_title("SMU current (mA) and voltage (V)", fontsize=self.font_title_size)

            # Format axes for data
            self.axes_1.xaxis.set_major_formatter(matplotlib.dates.DateFormatter('%M:%S'))
            self.axes_1.tick_params(axis='x', rotation=45)
            self.axes_2.xaxis.set_major_formatter(matplotlib.dates.DateFormatter('%M:%S'))
            self.axes_2.tick_params(axis='x', rotation=45)
            self.axes_3.xaxis.set_major_formatter(matplotlib.dates.DateFormatter('%M:%S'))
            self.axes_3.tick_params(axis='x', rotation=45)
            self.axes_1.xaxis_date()
            self.axes_2.xaxis_date()
            self.axes_3.xaxis_date()

            # Add horizontal lines to voltage plot
            self.axes_2.axhline(self.voltage_prediction[0], linestyle='--', color="purple")
            self.axes_2.axhline(self.voltage_prediction[1], linestyle='--', color="brown")

            # Update labels with values
            self.label_temp_1['text'] = "{:.2f}".format(float(temp_1))
            self.label_temp_2['text'] = "{:.2f}".format(float(temp_2))
            self.label_temp_3['text'] = "{:.2f}".format(float(temp_3))
            self.label_volt_1['text'] = "{:.2f}".format(float(volt_1) * 1000)
            self.label_volt_2['text'] = "{:.2f}".format(float(volt_2) * 1000)

    @staticmethod
    def tail(f, n, offset=None):
        """Reads a n lines from f with an offset of offset lines.  The return
        value is a tuple in the form ``(lines, has_more)`` where `has_more` is
        an indicator that is `True` if there are more lines in the file.
        """
        avg_line_length = 72 + 20
        to_read = n + (offset or 0)

        while 1:
            try:
                f.seek(-(avg_line_length * to_read), 2)
            except IOError:
                # woops.  apparently file is smaller than what we want
                # to step back, go to the beginning instead
                f.seek(0)
            pos = f.tell()
            lines = f.read().splitlines()
            if len(lines) >= to_read or pos == 0:
                return lines[-to_read:offset and -offset or None], \
                       len(lines) > to_read or pos > 0
            avg_line_length *= 1.3

    def get_data(self, arg2):
        temp_1 = self.protocol.send_command(0x02, [5])
        temp_2 = self.protocol.send_command(0x02, [6])
        temp_3 = self.protocol.send_command(0x02, [7])
        volt_1 = self.protocol.send_command(0x03, [0])
        volt_2 = self.protocol.send_command(0x03, [1])
        time_str = datetime.datetime.now().strftime('%d.%m.%Y %H:%M:%S')
        # Check that file exists
        if not os.path.exists(self.data_file_name):
            print("File does not exist. Creating new...")
            file = open(self.data_file_name, 'w+')
            file.close()

        file = open(self.data_file_name, 'a+')
        file.write(time_str + ',' + "{:.7f}".format(temp_1[0]) + ',' + "{:.7f}".format(temp_2[0]) + ',' +
                   "{:.7f}".format(temp_3[0]) + ',' + "{:.7f}".format(volt_1[0]) + ',' + "{:.7f}".format(volt_2[0]) +
                   ',' + "{:.7f}".format(self.res_1_value) + ',' + "{:.7f}".format(self.res_2_value) + ',' +
                   "{:.10f}".format(self.smu_msg[0]) + ',' + "{:.10f}".format(self.smu_msg[1]) + '\n')
        file.close()

    def update_data_file_name(self):
        # File name for data and final data
        if self.exp_flag.get():
            self.data_file_name = 'Results/exp_data_' + "{:.2f}".format(self.res_1_value) + '_' + "{:.2f}".format(
                self.res_2_value)+ '_' + "{:.1f}".format(self.target_temp_cold) + '_' + "{:.1f}".format(self.target_temp_hot) + '.txt'
        else:
            self.data_file_name = 'Results/data_' + datetime.datetime.now().strftime('%d_%m_%Y_%H_%M') + '.txt'

    def update_button_callback(self, arg2):

        self.target_temp_cold = float(self.entry_temp_1.get())
        self.target_temp_hot = float(self.entry_temp_2.get())
        self.res_1_value = float(self.entry_res_1.get())
        self.res_2_value = float(self.entry_res_2.get())
        self.voltage_prediction = self.calc_theoretical_voltages()
        self.update_data_file_name()
        self.protocol.send_command(0x04, [self.target_temp_hot])
        self.protocol.send_command(0x05, [self.target_temp_cold])

    def button_start_stop_callback(self, arg2):
        if self.button_start_stop['text'] == "Start":
            self.smu_thread.resume_smu()
            self.protocol = STMprotocol(self.entry_COM.get())
            self.button_start_stop['text'] = "Stop"
            self.res_1_value = float(self.entry_res_1.get())
            self.res_2_value = float(self.entry_res_2.get())
            self.target_temp_cold = float(self.entry_temp_1.get())
            self.target_temp_hot = float(self.entry_temp_2.get())
            self.update_data_file_name()
            self.pause = False

        elif self.button_start_stop['text'] == "Stop":
            self.smu_thread.pause_smu()
            with self.queue.mutex:
                self.queue.queue.clear()
            self.protocol.ser.close()
            self.button_start_stop['text'] = "Start"
            self.pause = True

    def button_clear_data_callback(self, arg2):
        if os.path.exists(self.data_file_name):
            os.remove(self.data_file_name)
        else:
            print("The file does not exist")


# def output(event):
#     txt = entry_1.get()
#     try:
#         if int(txt) < 18:
#             label_1["text"] = 'Go HOME'
#         else:
#             label_1["text"] = 'Andrey'
#     except ValueError:
#         label_1["text"] = 'Wrong value'


root = Tk()
root.title("Testbed GUI")
root.configure(background='white')
app = App(root)

# ani = animation.FuncAnimation(app.figure_1, app.animate, interval=1000)

root.mainloop()
