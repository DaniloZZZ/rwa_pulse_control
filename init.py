from qiskit import IBMQ

def _anl_provider():
    IBMQ.load_account()
    provider_anl = IBMQ.get_provider(hub='ibm-q-ornl', group='bes-qis',
                                     project='argonne')
    return provider_anl

def _open_provider():
    IBMQ.load_account()
    provider = IBMQ.get_provider(hub='ibm-q', group='open', project='main')
    return provider

def provider(which='open'):
    if which=='open':
        return _open_provider()
    elif which=='anl':
        return _anl_provider()

def backend(backend_name, provider_name='open'):
    print(f'Initializing IBMQ {backend_name}')
    p_ = provider(which=provider_name)
    backend = p_.get_backend(backend_name)
    return backend

def backend_open_pulse(backend_name='ibmq_armonk'):
    b  = backend(backend_name)
    backend_config = b.configuration()
    assert backend_config.open_pulse, "Backend doesn't support OpenPulse"
    return b

# samples need to be multiples of 16
def get_closest_multiple_of_16(num):
    return (int(num) - (int(num)%16))
