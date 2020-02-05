import numpy as np

from qiskit import pulse
from qiskit.pulse import pulse_lib
from qiskit import assemble
from qiskit.tools.monitor import job_monitor

def get_closest_multiple_of_16(num):
    return (int(num) - (int(num)%16))

def make_drive_pulse(dt, amp=.3, sigma=75):
    # Drive pulse parameters (us = microsecond)
    # This determines the actual width of the gaussians
    drive_sigma_ns = sigma
    # This is a truncating parameter
    drive_samples_ns = drive_sigma_ns*8

    drive_sigma = get_closest_multiple_of_16(drive_sigma_ns / dt)       # The width of the gaussian in units of dt
    drive_samples = get_closest_multiple_of_16(drive_samples_ns / dt)   # The truncating parameter in units of dt
    drive_amp = amp
    # Drive pulse samples
    drive_pulse = pulse_lib.gaussian(duration=drive_samples,
                                     sigma=drive_sigma,
                                     amp=drive_amp,
                                     name='freq_sweep_excitation_pulse')
    return drive_pulse

def make_meas_pulse(dt, samples=1000, sigma=28, amp=.25):
    meas_samples_ns = samples
    meas_sigma_ns = sigma
    # The width of the gaussian part of the rise and fall
    meas_risefall_ns = 100
    # and the truncating parameter: how many samples to dedicate to the risefall

    meas_samples = get_closest_multiple_of_16(meas_samples_ns / dt)
    meas_sigma = get_closest_multiple_of_16(meas_sigma_ns / dt)       # The width of the gaussian part in units of dt
    meas_risefall = get_closest_multiple_of_16(meas_risefall_ns / dt) # The truncating parameter in units of dt

    meas_amp = amp
    # Measurement pulse samples
    meas_pulse = pulse_lib.gaussian_square(duration=meas_samples,
                                           sigma=meas_sigma,
                                           amp=meas_amp,
                                           risefall=meas_risefall,
                                           name='measurement_pulse')
    return meas_pulse

def freq_sweep_schedule(qbit, backend_config, drive_chan,
                        meas_samples=1000,):
    dt = backend_config.dt
    print(f"Sampling time: {dt} ns")

    drive_pulse = make_drive_pulse(dt)
    meas_pulse = make_meas_pulse(dt, samples=meas_samples)
    ### Construct the acquire pulse to trigger the acquisition
    # Acquire pulse samples
    acq_cmd = pulse.Acquire(duration=meas_samples)
    # Find out which group of qubits need to be acquired with this qubit
    meas_map_idx = None
    for i, measure_group in enumerate(backend_config.meas_map):
        if qbit in measure_group:
            meas_map_idx = i
            break
    assert meas_map_idx is not None, f"Couldn't find qubit {qbit} in the meas_map!"


    ### Collect the necessary channels
    #drive_chan = pulse.DriveChannel(qbit)
    meas_chan = pulse.MeasureChannel(qbit)
    #acq_chan = pulse.AcquireChannel(qbit)

    schedule = pulse.Schedule(name='Frequency sweep')
    schedule += drive_pulse(drive_chan)
    measure_schedule = meas_pulse(meas_chan)
    # Trigger data acquisition, and store measured values into respective memory slots
    measure_schedule += acq_cmd([pulse.AcquireChannel(i) for i 
                                 in backend_config.meas_map[meas_map_idx]],
                                [pulse.MemorySlot(i) for i 
                                 in backend_config.meas_map[meas_map_idx]])

    # shift the start time of the schedule by some duration
    schedule += measure_schedule << schedule.duration
    schedule += drive_pulse(drive_chan)<< schedule.duration - drive_pulse.duration
    schedule += measure_schedule << drive_pulse.duration

    return schedule

### Get sampling time

def sweep_program(backend, frequencies=None
               ,qbit=0
               ):
    backend_config = backend.configuration()
    backend_defaults = backend.defaults()

    ## Get qubit frequency
    center_est_freq = backend_defaults.qubit_freq_est[qbit]
    print(f'Estimated frequency for qbit {qbit} is {center_est_freq}')
    freq_span = .02
    count = 50

    if not frequencies:
        frequencies = np.linspace(center_est_freq-freq_span/2,
                                  center_est_freq+freq_span/2,
                                  count
                              )
    drive_chan = pulse.DriveChannel(qbit)
    schedule = freq_sweep_schedule(qbit, backend_config, drive_chan)
    # Create the frequency settings for the sweep (MUST BE IN HZ)
    schedule_frequencies = [{drive_chan: freq} for freq in frequencies]

    num_shots_per_frequency = 1024
    frequency_sweep_program = assemble(schedule,
                                       backend=backend, 
                                       meas_level=1,
                                       meas_return='avg',
                                       shots=num_shots_per_frequency,
                                       schedule_los=schedule_frequencies)
    return frequency_sweep_program

#schedule.draw(channels_to_plot=[drive_chan, meas_chan], label=True, scaling=1.0)

def qbit_freqs(backend, frequencies, qbit=0):
    frequency_sweep_program = sweep_program(backend, frequencies, qbit)

    job = backend.run(frequency_sweep_program)

    job_monitor(job)
    job.error_message()

    return job.result(timeout=120)
