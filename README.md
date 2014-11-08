tracermppt
==========

This is a Python module for interacting with the Tracer-2210RN solar charge
controller via serial.  It should also work with other charge controllers that
can use the MT-5 remote monitoring accessory.

The RM (remote monitoring) port should be connected to a 3.3V TTL serial port,
such as [this SparkFun adapter board](https://www.sparkfun.com/products/9873).
It should be wired as follows.  Ethernet wire colors correspond to the T-568B
standard found on most common patch cables:

| Charger pin | Ethernet color       | Function         | FTDI adapter pin |
| ----------- | -------------------- | ---------------- | ---------------- |
| 5           | white/blue           | Transmitted data | 5 (RXD)          |
| 6           | green                | Received data    | 4 (TXD)          |
| 7 or 8      | brown or white/brown | Ground           | 1 (Ground)       |

Basic usage is as follows:

```
In [1]: import tracermppt

In [2]: t = tracermppt.Tracer("/dev/ttyUSB2")

In [3]: t.read_realtime()
Out[3]: 
{'battery_full': True,
 'battery_full_voltage': 14.27,
 'battery_overload': False,
 'battery_temperature': 31,
 'battery_voltage': 14.31,
 'charge_current': 0.68,
 'charging': True,
 'load_current': 0.16,
 'load_on': True,
 'load_short': False,
 'over_discharge': False,
 'overdischarge_voltage': 11.15,
 'overload': False,
 'pv_voltage': 16.26}
```

You can also switch the output on and off:

```
In [4]: t.set_load_on(False)
Out[4]: {'load_on': False}

In [5]: t.set_load_on(True)
Out[5]: {'load_on': True}
```

The command for setting the timer parameters is not currently implemented, as
my application does not require it.



