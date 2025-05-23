# ------------------------------------------------------------------------------
# SRLP Network / Doubling Water Supply Example
# ------------------------------------------------------------------------------

import numpy as np
from matplotlib import pyplot as plt
import importlib
#plt.ion()
plt.ioff()

import srlp

#%load_ext autoreload
#%autoreload

importlib.reload(srlp)
#del net

dt = 3.15E7*10
_B = 100 # uniform

nseg = 5
numel = [5, 7, 4, 8, 10]

upstream_segment_IDs = [[], [], [0,1], [], [2,3]]
downstream_segment_IDs = [[2], [2], [4], [4], []]

# SRLP
D = 0.5E-3        # 0.5 mm 
n = 0.025         # 0.025 or 0.02
C_f = 0.1
tau_crit_bank = 2 # 2 Pa

z = []
#Q_in_list = [5., 5., 10., 5, 15.]
# Test constant 
Q_in_list = [5., 5., 10., 10., 20.]
#Q_in_list = [5., 5., 5., 5, 5.]
Q_in_list = [[2.5, 2.5, 2.5, 5, 5], [7.5, 7.5, 7.5, 7.5, 5, 5, 5], 10, 10., 20.]
Q_in_list = [[2.5, 2.5, 2.5, 5, 5],
             [7.5, 7.5, 7.5, 7.5, 5, 5, 5],
             [10, 11, 13, 14],
             [10., 11, 13, 14, 17, 21, 22, 25],
             [39., 40., 41., 42., 43., 44., 45., 45., 46., 47.]]
Q = []
B = []
print( "" )
print( "**************" )
print( "" )
for i in range(nseg):
    # Start z as all zeros
    z.append( np.zeros( numel[i] ) )
    # Start Q as constant within each segment
    Q.append( Q_in_list[i] * np.ones( numel[i] ) )
    # Uniform valley width: Simpler for example
    B.append( _B * np.ones( numel[i] ) )
    print( numel[i] )
print( "" )
print( "**************" )
print( "" )

# Custom for just this test network
x = [
      1000 * np.array([2, 4, 6.5, 9, 10]),
      1000 * np.array([0, 1, 2, 3, 6, 8, 10.5]),
      1000 * np.array([12, 15, 18, 20]),
      1000 * np.array([2, 6, 8, 12, 14, 16, 18, 20]),
      1000 * np.array([23, 24, 25, 26, 27, 28, 29, 30, 31, 32])
    ]

dQ = []
for Qseg in Q:
    dQ.append( 0. )

"""
# Uniform dx test
# Custom for just this test network
x = [
      1000 * np.array([2, 4, 6, 8, 10]),
      1000 * np.array([-2, 0, 2, 4, 6, 8, 10]),
      1000 * np.array([12, 14, 16, 18]),
      1000 * np.array([4, 6, 8, 10, 12, 14, 16, 18]),
      1000 * np.array([20, 22, 24, 26, 28, 30])
    ]
"""

# Base level
x_bl = 1000*33
z_bl = 0

# Upstream boundary condition: 1.5% grade
S0 = [0.015, 0.015, 0.015]

# Instantiate network object
net = srlp.Network()
self = net # For debugging, etc.

# Initialize network by passing x, z, etc. information to model
net.initialize(
                config_file = None,
                x_bl = x_bl,
                z_bl = z_bl,
                S0 = S0,
                Q_s_0 = None,
                upstream_segment_IDs = upstream_segment_IDs,
                downstream_segment_IDs = downstream_segment_IDs,
                x = x,
                z = z,
                Q = Q,
                dQ = dQ,
                B = B,
                D = D,
                n = n,
                C_f = C_f,
                tau_crit_bank = tau_crit_bank,
                overwrite=False
                )


# Should do this above
net.set_niter(1)
net.get_z_lengths()

net.evolve_threshold_width_river_network(nt=100, dt=100*dt)

for lp in net.list_of_LongProfile_objects:
    # If not downstream-most segment
    if len( lp.downstream_segment_IDs ) > 0:
        for _id in lp.downstream_segment_IDs:
            dsseg = net.list_of_LongProfile_objects[_id]
            _xjoin = [lp.x[-1], dsseg.x[0]]
            _zjoin = [lp.z[-1], dsseg.z[0]]
            plt.plot(_xjoin, _zjoin, 'k-', linewidth=4, alpha=.5)
    else:
        plt.plot(lp.x_ext[0][-2:], lp.z_ext[0][-2:], 'k-', linewidth=4, alpha=.5)
    plt.plot(lp.x, lp.z, '-', linewidth=4, alpha=.5)#, label=lp.)

# ---- Double water supply

# As with sediment supply, there is currently not a neat way to change
# discharge.
# We need to change the slope at the channel heads as before (this time to
# double water supply we need to change slope by a factor 0.5^(6/7)).
new_S0 = [
    net.list_of_LongProfile_objects[i].S0*(0.5**(6./7.))
        for i in net.list_of_channel_head_segment_IDs
    ]
net.update_z_ext_external_upstream(S0 = new_S0)

# We also need to update discharge on all the segments.
# I copied this chunk from the 'initialize' function, where it sets the
# discharge.

#new_Q = [seg.Q*2. for seg in net.list_of_LongProfile_objects]
#net.update_Q(new_Q)
#net.create_Q_ext_lists()
#net.update_Q_ext_from_Q()
#net.update_Q_ext_internal()
#net.update_Q_ext_external_upstream() 
#net.update_Q_ext_external_downstream()
#net.update_dQ_ext_2cell()

nsteps = 200
for i in range(nsteps):
    net.evolve_threshold_width_river_network(nt=1, dt=10*dt)
    if i % np.ceil(nsteps/50) == 0:
        for lp in net.list_of_LongProfile_objects:
            # If not downstream-most segment
            if len( lp.downstream_segment_IDs ) > 0:
                for _id in lp.downstream_segment_IDs:
                    dsseg = net.list_of_LongProfile_objects[_id]
                    _xjoin = [lp.x[-1], dsseg.x[0]]
                    _zjoin = [lp.z[-1], dsseg.z[0]]
                    plt.plot(_xjoin, _zjoin, 'k-', linewidth=1, alpha=1)
            else:
                plt.plot(lp.x_ext[0][-2:], lp.z_ext[0][-2:], 'k-', linewidth=1, alpha=1)
            plt.plot(lp.x, lp.z, 'k-', linewidth=1, alpha=.2)#, label=lp.)

for lp in net.list_of_LongProfile_objects:
    # If not downstream-most segment
    if len( lp.downstream_segment_IDs ) > 0:
        for _id in lp.downstream_segment_IDs:
            dsseg = net.list_of_LongProfile_objects[_id]
            _xjoin = [lp.x[-1], dsseg.x[0]]
            _zjoin = [lp.z[-1], dsseg.z[0]]
            plt.plot(_xjoin, _zjoin, 'k-', linewidth=3, alpha=.5)
    else:
        plt.plot(lp.x_ext[0][-2:], lp.z_ext[0][-2:], 'k-', linewidth=3, alpha=.5)
    plt.plot(lp.x, lp.z, 'k-', linewidth=3, alpha=.5)#, label=lp.)

plt.xlabel('Distance downvalley in network [m]', fontsize=14)
plt.ylabel('Elevation above outlet [m]', fontsize=14)
plt.tight_layout()
plt.savefig('Qwx2.pdf') 
plt.show()

#"""

