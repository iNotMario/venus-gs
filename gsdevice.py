#!/usr/bin/env python3
import sys
import dbus
import dbus.mainloop.glib
import time
import logging
import requests
import datetime


from gi.repository import GLib                       
dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

sys.path.insert(0, '/opt/victronenergy/vrmlogger/ext/velib_python')
from vedbus import VeDbusService

logging.getLogger().setLevel(logging.INFO)

baseurl = sys.argv[1]                                                                                                       
baseinstance = int(sys.argv[2]) if len(sys.argv) > 2 else 50

class Unitizer:
    total = 0
    time_unit = datetime.timedelta(milliseconds = 1000)
    time_last = datetime.datetime.now()
    def __init__(self, u, t = 0):
        self.time_unit = u
        self.total = t
    def get(self):
        return self.total
    def add(self, v):
        ct = datetime.datetime.now()
        lt = self.time_last
        dt = ct - lt
        du = dt.total_seconds() / self.time_unit.total_seconds()
        self.total += v * du
        
        self.time_last = ct 
        return self.get()

class Roll:
	def __init__(self, n, v=None):
		self.v = v
		self.n = n

	def add(self, x):
		tot = (self.v or x) * self.n
		self.v = (tot + x) / (self.n + 1)

		return self.v

class Value(dbus.Double):
	def __new__(cls, v, f):
		return super(Value, cls).__new__(cls, v)
	def __init__(self, v, f):
		dbus.Double.__init__(v)
		self.f = f
	def __str__(self):
		return str(self.f) % self

class Device:
	proxy=None
	def __init__(self, type, id, name, ident=None, conn=baseurl):
		self.bus = dbus.SystemBus(private=True)
		self.id = id
		self.ident = ident or 'gs_%s' % (id)
		self.name = 'com.victronenergy.%s.%s' % (type, self.ident)

		logging.info('[%-40s] Initializing [%s] as a [%s] with instance %d', self.name, name, type, id)

		self.svc = VeDbusService(self.name, self.bus)
		self.svc.add_path('/Mgmt/ProcessName', 'gsdevice.py')
		self.svc.add_path('/Mgmt/ProcessVersion', '1.0')
		self.svc.add_path('/Mgmt/Connection', conn)
		self.svc.add_path('/DeviceInstance', id)
		self.svc.add_path('/ProductId', 0xFFFF)
		self.svc.add_path('/ProductName', name)
		self.svc.add_path('/CustomName', name)
		self.svc.add_path('/Model', name)
		self.svc.add_path('/Connected', 1)
		self.svc.add_path('/Role', type)
		self.svc.add_path('/HardwareVersion', '0.0.0')
		self.svc.add_path('/FirmwareVersion', '0.0.0')
		self.svc.add_path('/Serial', 'GS%d' % id)

	def set_path(self, path, value, writeCallback=None):
		logging.debug('[%-40s] Setting %s to %s', self.name, path, value)
		if not path in self.svc:
			logging.info('[%-40s] Exporting %-40s initially as %s', self.name, path, value)
			self.svc.add_path(path, None, writeable=(writeCallback is not None), onchangecallback=writeCallback)

		proxy = self.proxy or self.svc
		proxy[path] = value
	def set_mode(self, path, mode):
		print((path, mode))

	def __enter__(self):
		self.proxy = self.svc.__enter__()
		return self

	def __exit__(self, *exc):
		self.proxy = None
		self.svc.__exit__(exc)

def inverter_command(cmd):
	if cmd is None: return False
	logging.info('Inverter Command: %s', cmd)
	x = requests.post(baseurl + '/cmd', data = {'cmd': cmd}, timeout = 5)
	time.sleep(1)
	return x

def ftoc(val):
	return (val - 32)  * (5/9)

temperature = Device('temperature', baseinstance + 1, 'GS Temperature')
temperature.set_path('/ProductId', 0xa162)
temperature.set_path('/TemperatureType', 2)
temperature.set_path('/Status', 0)
temperature.set_path('/Temperature', None)

fanA = Device('tank', baseinstance + 5, 'GS Fan A')
fanA.set_path('/ProductId', 41313)
fanA.set_path('/FluidType', 2)
fanA.set_path('/Level', None)
fanA.set_path('/Temperature', None)
fanB = Device('tank', baseinstance + 6, 'GS Fan B')
fanB.set_path('/ProductId', 41313)
fanB.set_path('/FluidType', 2)
fanB.set_path('/Level', None)
fanB.set_path('/Temperature', None)
fanC = Device('tank', baseinstance + 7, 'GS Fan C')
fanC.set_path('/ProductId', 41313)
fanC.set_path('/FluidType', 2)
fanC.set_path('/Level', None)
fanC.set_path('/Temperature', None)
fanD = Device('tank', baseinstance + 8, 'GS Fan D')
fanD.set_path('/ProductId', 41313)                                                                                                                            
fanD.set_path('/FluidType', 2)                                                                                                                                
fanD.set_path('/Level', None)
fanD.set_path('/Temperature', None)

inverter = Device('vebus', baseinstance + 0, 'GS Inverter')
inverter.set_path('/Ac/NumberOfPhases', 1)
inverter.set_path('/Ac/NumberOfAcInputs', 1)
inverter.set_path('/Ac/ActiveIn/ActiveInput', 0)                           
inverter.set_path('/State', None)
inverter.set_path('/Ac/PowerMeasurementType', 4)

def set_input_limitI(path, limit):
	try:
		logging.info('Informed to set Input Limit to %s', limit)
		inverter.set_path('/Ac/ActiveIn/CurrentLimit', limit)
	except:
		logging.info('... failed')

inverter.set_path('/Ac/ActiveIn/CurrentLimitIsAdjustable', 1)
inverter.set_path('/Ac/ActiveIn/CurrentLimit', 25, set_input_limitI)

def set_mode(path, mode):
	try:
		logging.debug('Informed to set mode... %s', mode)
		cmd = ['ATSinv','PWRoff'] if mode == 4 else ['ATSac','CHGoff'] if mode == 3 else ['ATSinv','PWRon'] if mode == 2 else ['ATSac','CHGblk'] if mode == 1 else None
		status = [inverter_command(x) for x in cmd]
		if cmd is not None:
			inverter.set_path('/Mode', mode)
	except:
		logging.info('... failed')

inverter.set_path('/ModeIsAdjustable', 1)
inverter.set_path('/Mode', None, set_mode)

rn = 10
inverter.p_in = Roll(rn)
inverter.p_ou = Roll(rn)
inverter.i_dc = Roll(rn)

inverter.d_io = Unitizer(datetime.timedelta(hours = 1))                                                                                                    
inverter.d_iv = Unitizer(datetime.timedelta(hours = 1))                                                                      
inverter.d_vo = Unitizer(datetime.timedelta(hours = 1))

def update():
	try:
		stats = requests.get(url=baseurl + '/stats.json', timeout = 10).json()
		f_in = stats['outputs']['outHZ']
		v_in = stats['inputs']['inV']
		i_in = stats['inputs']['inA']
		p_in = v_in * i_in

		f_ou = stats['outputs']['outHZ']
		v_ou = stats['outputs']['outV']
		i_ou = stats['outputs']['outA']
		p_ou = stats['outputs']['outW']

		e_tf = stats['outputs']['xfEFF'] / 100
		i_tf = stats['inputs']['xfA']
		
		v_dc = stats['inputs']['battV']
		i_dc = (p_in - p_ou) / v_dc
		p_dc = v_dc * i_dc

		p_total = stats['stats']['KWh']

		t_tta = stats['temps']['TTA']
		t_ttb = stats['temps']['TTB']
		t_tma = stats['temps']['TMA']
		t_tmb = stats['temps']['TMB']

		f_fa = stats['fans']['FA']
		f_fb = stats['fans']['FB']
		f_fc = stats['fans']['FC']
		f_fd = 0 #No such Fan

		s_inv = stats['stats']['invSTATES'] & 0xF
		f_inv = stats['stats']['inFLAGS']
		m_ats = s_inv == 1
		m_chg = 4 if not f_inv & 0x10 else 3 if f_inv & 0x20 else 1

		##With Off meaning Passthru
		m_ve = 2 if not m_ats else m_chg
		s_ve = 3 if m_ve == 1 else 9 if m_ve == 2 else 5 if m_ve == 3 else 8 if m_ve == 4 else None

		##With Off meaning Off
		m_ve = 4 if s_inv == 0x3 else 2 if s_inv == 0x2 else 3 if s_inv == 0x1 and m_chg == 4 else 1 if s_inv == 0x1 else None
		s_ve = 3 if m_ve == 1 else 9 if m_ve == 2 else 8 if m_ve == 3 else 0 if m_ve == 4 else None

		a_alarms = {}
		a_alarms_alms = stats['errors']['Alms']
		a_alarms_bits = { ##Bearing in mind this is TCP based... if carrier is lost from outage, we can't access it...
			0  : ('/Alarms/TemperatureSensor', 1), #"Xfrmr Temp",
			1  : ('/Alarms/TemperatureSensor', 1), #"MOS Temp",
			2  : ('/Alarms/L1/Overload',       1), #"Overload",	
			3  : ('/Alarms/VoltageSensor',     1), #"Output Volt",
			4  : ('/Alarms/LowBattery',        1), #"Batt. Low",
			5  : ('/Alarms/VoltageSensor',     1), #"Batt. High",
			6  : ('/Alarms/PhaseRotation',     1), #"Input Freq.",
			7  : ('/Alarms/GridLost',          1), #"Input Volt",
			8  : ('/Alarms/HighTemperature',   2), #"OVERHEAT",
			9  : ('/Alarms/L1/Overload',       2), #"OVERLOAD LO",
			10 : ('/Alarms/L1/Overload',       2), #"OVERLOAD HI",
		}
		for b, (path, value) in a_alarms_bits.items(): a_alarms[path] = value if (a_alarms_alms & 1<<b) else 0

		with inverter as inverterP, fanA as fanAP, fanB as fanBP, fanC as fanCP, fanD as fanDP, temperature as temperatureP:
			for     path, value  in a_alarms.items():      inverterP.set_path(path, value) #Dictionary prevents spamming dbus...
			temperatureP.set_path('/Temperature', ftoc(max(t_tta, t_ttb, t_tma, t_tmb)))

			inverterP.set_path('/ModeIsAdjustable', 1)
			inverterP.set_path('/Ac/ActiveIn/CurrentLimitIsAdjustable', 1)

			inverterP.set_path('/Mode', m_ve)  ##VE Translated Mode, 1,2,3,4 => Charge Only, Inverter Only, On, Off
			inverterP.set_path('/State', s_ve) ##VE Translated State, 0=Off;1=Low Power;2=Fault;3=Bulk;4=Absorption;5=Float;6=Storage;7=Equalize;8=Passthru;9=Inverting;10=Power assist;11=Power supply

			inverterP.set_path('/Debug/m_ats', m_ats)
			inverterP.set_path('/Debug/m_chg', m_chg)
			inverterP.set_path('/Debug/m_ve', m_ve)
			inverterP.set_path('/Debug/s_inv', s_inv)
			inverterP.set_path('/Debug/f_inv', f_inv)

			inverterP.set_path('/Ac/Out/L1/V', Value(v_ou, '%.2f V'))
			inverterP.set_path('/Ac/Out/L1/I', Value(i_ou, '%.2f A'))
			inverterP.set_path('/Ac/Out/L1/P', Value(p_ou, '%.2f W'))
			inverterP.set_path('/Ac/Out/L1/F', Value(f_ou, '%.2f Hz'))

			inverterP.set_path('/Ac/ActiveIn/L1/V', Value(v_in, '%.2f V'))
			inverterP.set_path('/Ac/ActiveIn/L1/I', Value(i_in, '%.2f A'))
			inverterP.set_path('/Ac/ActiveIn/L1/P', Value(p_in, '%.2f W'))
			inverterP.set_path('/Ac/ActiveIn/L1/F', Value(f_in, '%.2f Hz'))

			inverterP.set_path('/Dc/0/Voltage', Value(v_dc, '%.2f V'))
			inverterP.set_path('/Dc/0/Current', Value(i_dc, '%.2f A'))
			inverterP.set_path('/Dc/0/Power', Value(p_dc, '%.2f W'))

			#inverterP.set_path('/Energy/InverterToAcOut', Value(p_total, '%.6f kWh'))

			d_io = p_ou  - max(0, -p_dc)
			d_iv = p_in  - p_ou
			d_vo = p_ou  - p_in

			inverter.d_io.add(max(0, d_io))
			inverter.d_iv.add(max(0, d_iv))
			inverter.d_vo.add(max(0, d_vo))

			inverterP.set_path('/Debug/d_io', Value(d_io, '%f W'))
			inverterP.set_path('/Debug/d_iv', Value(d_iv, '%f W'))
			inverterP.set_path('/Debug/d_vo', Value(d_vo, '%f W'))
			
			inverterP.set_path('/Energy/AcIn1ToAcOut',    Value(inverter.d_io.get() / 1000, '%.6f kWh'))
			inverterP.set_path('/Energy/AcIn1ToInverter', Value(inverter.d_iv.get() / 1000, '%.6f kWh'))
			inverterP.set_path('/Energy/InverterToAcOut', Value(inverter.d_vo.get() / 1000, '%.6f kWh'))

			fanAP.set_path('/Level', f_fa)
			fanAP.set_path('/Temperature', ftoc(t_tta))
			fanBP.set_path('/Level', f_fb)
			fanBP.set_path('/Temperature', ftoc(t_ttb))
			fanCP.set_path('/Level', f_fc)
			fanCP.set_path('/Temperature', ftoc(t_tma))
			fanDP.set_path('/Level', f_fd)
			fanDP.set_path('/Temperature', ftoc(t_tmb))

	except IOError as e:
		print('Unable to get data... %s' % str(e))
	except Exception as e:
		print('Unknown Exception... %s' % e)

	return True

def main():
	mainloop = GLib.MainLoop()
	GLib.timeout_add(1000, update)
	mainloop.run()

main()
