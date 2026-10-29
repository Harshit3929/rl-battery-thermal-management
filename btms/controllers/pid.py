"""A tuned temperature PID with explicit ambient-aware actuator routing."""
import numpy as np


class PID:
    def __init__(self, setpoint=36., kp=.2, ki=.001, kd=0., dt=5.):
        self.setpoint, self.kp, self.ki, self.kd, self.dt = setpoint, kp, ki, kd, dt
        self.integral = 0.
        self.previous = None

    def act(self, observation):
        error = float(max(observation[:4])) - self.setpoint
        derivative = 0. if self.previous is None else (error-self.previous)/self.dt
        candidate = self.integral + error*self.dt
        output = self.kp*error + self.ki*candidate + self.kd*derivative
        if 0 <= output <= 1 or (output>1 and error<0) or (output<0 and error>0):
            self.integral = candidate
        demand = float(np.clip(self.kp*error+self.ki*self.integral+self.kd*derivative, 0, 1))
        self.previous = error
        ambient, coolant = observation[6], observation[8]
        fan = demand if coolant > ambient+1 else 0.
        valve = demand if ambient >= self.setpoint-3 else 0.
        return np.array([np.sqrt(demand), fan, valve])
