import math
import random
import wsnsimpy.wsnsimpy_tk as wsp
import enum

BROADCAST_DELAY = .1

class Status(enum.Enum):
    UNDEFINED = 0
    MEMBER = 1
    CLUSTER_HEAD = 2

class Message(enum.Enum):
    NODE_RESIDUAL = 1
    I_AM_CLUSTER_HEAD = 2
    I_AM_CLUSTER_MEMBER = 3
    CLUSTER_HEAD_RESIDUAL = 4
    ROUTE_TO_SINK = 5

###########################################################
class MyNode(wsp.Node):
    tx_range = 100

    status = Status.UNDEFINED
    chsv_neighbors = {}
    psv_neighbors = {}
    chsv_point = 0
    psv_point = 0
    # self.pin = 1000
    ############
    # for member
    cluster_heads = []
    cluster_head_official = None
    # for cluster head
    psv_neighbors = {}
    members = []
    cluster_adjacency = {}
    data_combine = None
    route_to_sink = {}

    ###################
    def __init__(self, sim, id, pos):
        super().__init__(sim, id, pos)

    def init(self):
        super().init()
        self.status = Status.UNDEFINED
        self.chsv_neighbors = {}
        self.psv_neighbors = {}
        self.chsv_point = 1000
        self.psv_point = 1000
        # self.pin = 1000
        ############
        # for member
        self.cluster_heads = []
        self.cluster_head_official = None
        # for cluster head
        self.psv_neighbors = {}
        self.members = []
        self.cluster_adjacency = {}
        self.route_to_sink = {}

    ###################
    def run(self):
        if self.id is SINK_NODE:
            self.scene.nodecolor(self.id, 0, 0, 0)
            self.scene.nodewidth(self.id, 2)
            yield self.timeout(1)
        else:
            self.scene.nodecolor(self.id, 0.7, 0.7, 0.7)
            self.sim.env.process(self.setup_phase())
            self.sim.env.run(until=0.8)
        self.sim.env.process(self.steady_phase())

    ###################
    def setup_phase(self):
        self.chsv_point = self.calculate_chsv()
        yield self.timeout(BROADCAST_DELAY)
        self.send(wsp.BROADCAST_ADDR, msg=Message.NODE_RESIDUAL, src=self.id, chsv=self.chsv_point)

        yield self.timeout(.2)

        if len(self.chsv_neighbors) == 0 or self.chsv_point >= max(self.chsv_neighbors.values()):
            self.switch_state(Status.CLUSTER_HEAD)
            yield self.timeout(BROADCAST_DELAY)
            self.send(wsp.BROADCAST_ADDR, msg=Message.I_AM_CLUSTER_HEAD, src=self.id)

    def steady_phase(self):
        if self.id is SINK_NODE:
            for node in self.cluster_heads:
                self.send(node, msg=Message.ROUTE_TO_SINK, src=self.id, hop_count=1, path=[SINK_NODE])

        elif self.status == Status.MEMBER:
            # self.scene.clearlinks()
            seq = 0
            yield self.timeout(BROADCAST_DELAY)
            self.send(wsp.BROADCAST_ADDR, msg="My cluster heads", src=self.id, cluster_heads=self.cluster_heads)
            self.log(f"Cluster head: {self.cluster_heads}")
            # while True:
            #     yield self.timeout(BROADCAST_DELAY + random.uniform(0.1, 0.7))
            #     # self.log(f"Send data to {SINK_NODE} (via {self.cluster_head_official}) - seq {seq}")
            #     self.send(self.cluster_head_official, msg='Data', src=self.id, seq=seq)
            #     seq += 1

        elif self.status == Status.CLUSTER_HEAD:
            seq = 0
            self.data_combine = ''
            yield self.timeout(1)

            self.log(self.route_to_sink)

            while True:
                seq += 1
                if len(self.route_to_sink) == 0:
                    pass
                elif self.id < 10:
                    self.timeout(BROADCAST_DELAY + random.uniform(0.1, 0.4))
                    self.send_back_to_sink(msg='Data_Combine', src=self.id,
                                           seq=seq, data=self.data_combine)

                self.data_combine = ''
                yield self.timeout(1.5)
        # yield self.switch_state(Status.UNDEFINED)

    ###################
    def on_receive(self, sender, msg, src, **kwargs):
        global SINK_NODE

        if self.id is SINK_NODE:
            if msg == "Data_Combine":
                seq = kwargs['seq']
                data = kwargs['data']
                self.log(f"Got data from {sender} - seq {seq}: {data}")
            elif msg == 'Cluster information':
                self.log(f'Receive from {sender}: {kwargs["data"]}')
            elif msg == Message.I_AM_CLUSTER_HEAD:
                self.cluster_heads.append(src)
                self.cluster_head_official = src

        elif self.status is Status.CLUSTER_HEAD:
            if msg == Message.I_AM_CLUSTER_MEMBER:
                if self.id == kwargs['cluster_head']:
                    self.members.append(src)
                    self.scene.addlink(sender, self.id, "CH")
            elif msg == "My cluster heads":
                heads = kwargs['cluster_heads']
                for h in heads:
                    if h != self.id:
                        if h in self.cluster_adjacency:
                            self.cluster_adjacency[h].append(src)
                        else:
                            self.cluster_adjacency[h] = [src]
                        self.scene.addlink(h, src, "GW")
            elif msg == Message.CLUSTER_HEAD_RESIDUAL:
                self.psv_neighbors[src] = kwargs["psv_point"]
            elif msg == "Data":
                seq = kwargs['seq']
                self.data_combine += f'\nSource {src}: seq {seq}'
            elif msg == "Data_Combine":
                self.data_combine += f'\nData from Cluster {src}: \n{kwargs["data"]}'
                if len(self.route_to_sink) > 0:
                    self.timeout(BROADCAST_DELAY)
                    self.send_back_to_sink(msg='Data_Combine', seq=kwargs['seq'],
                                           src=self.id, data=self.data_combine)
                    self.data_combine = ""

            elif msg == Message.ROUTE_TO_SINK:
                hop_count = kwargs["hop_count"]
                path = kwargs["path"]
                if self.id in path:
                    return
                if (src in self.route_to_sink) and (hop_count >= self.route_to_sink[src]):
                    return
                self.route_to_sink[src] = hop_count + 1
                self.scene.addlink(self.id, src, "SINK")
                path.append(self.id)
                self.log(path)
                for node in self.cluster_adjacency.keys():
                    self.send_to_cluster_adjacency(msg=Message.ROUTE_TO_SINK, src=self.id,
                                                   chdest=node, hop_count=hop_count + 1, path=path)

        elif self.status is Status.MEMBER:
            if msg == Message.I_AM_CLUSTER_HEAD:
                self.cluster_heads.append(src)
            elif msg == Message.CLUSTER_HEAD_RESIDUAL:
                dest = kwargs["chdest"]
                yield self.timeout(BROADCAST_DELAY)
                self.send(dest, msg=msg, src=src, **kwargs)
            elif msg == "Data_Combine":
                dest = kwargs["chdest"]
                yield self.timeout(BROADCAST_DELAY)
                self.send(dest, msg=msg, src=src, **kwargs)
            elif msg == Message.ROUTE_TO_SINK:
                dest = kwargs["chdest"]
                yield self.timeout(BROADCAST_DELAY)
                self.send(dest, msg=msg, src=src, **kwargs)
        elif self.status is Status.UNDEFINED:
            if msg == Message.NODE_RESIDUAL:
                self.chsv_neighbors[src] = kwargs['chsv']
            elif msg == Message.I_AM_CLUSTER_HEAD:
                self.switch_state(Status.MEMBER)
                self.cluster_heads.append(src)
                self.cluster_head_official = src
                yield self.timeout(BROADCAST_DELAY)
                self.send(wsp.BROADCAST_ADDR, msg=Message.I_AM_CLUSTER_MEMBER, src=self.id,
                          cluster_head=self.cluster_head_official)
            elif msg == Message.I_AM_CLUSTER_MEMBER:
                if sender in self.chsv_neighbors:
                    del self.chsv_neighbors[sender]
                if len(self.chsv_neighbors) == 0 or self.chsv_point >= max(self.chsv_neighbors.values()):
                    self.switch_state(Status.CLUSTER_HEAD)
                    # self.log(f'Start broadcast CH message')
                    yield self.timeout(BROADCAST_DELAY)
                    self.send(wsp.BROADCAST_ADDR, msg=Message.I_AM_CLUSTER_HEAD, src=self.id)
        else:
            pass

    ###################
    def switch_state(self, status: Status):
        if status == Status.CLUSTER_HEAD:
            # set up cluster head UI
            self.status = Status.CLUSTER_HEAD
            self.scene.nodecolor(self.id, 0, 1, 0)
            self.scene.nodewidth(self.id, 2)
            self.scene.circle(
                self.pos[0], self.pos[1],
                self.tx_range)

            # init value
            self.members = []
            self.cluster_adjacency = {}

        elif status == Status.MEMBER:
            # set up cluster member UI
            self.scene.nodecolor(self.id, 1, 0, 0)
            self.scene.nodewidth(self.id, 2)

            # init value
            self.status = Status.MEMBER
            self.cluster_heads = []

        elif status == Status.UNDEFINED:
            self.scene.clearlinks()
            self.scene.nodecolor(self.id, 0.7, 0.7, 0.7)
            self.init()

    ###################
    def send_back_to_sink(self, msg, src, **kwargs):
        if len(self.route_to_sink) == 0:
            return

        parent = min(self.route_to_sink, key=self.route_to_sink.get)
        if parent != SINK_NODE:
            self.send_to_cluster_adjacency(msg=msg, src=src, chdest=parent, **kwargs)
        else:
            self.send_data_to_sink(msg=msg, src=src, **kwargs)

    def send_to_cluster_adjacency(self, msg, src, chdest, **kwargs):
        gw_node = self.cluster_adjacency[chdest][0]
        self.send(gw_node, msg=msg, src=src, chdest=chdest, **kwargs)

    def send_data_to_sink(self, msg, src, **kwargs):
        # self.log(f"Forward data from {src} to {SINK_NODE} - seq {kwargs['seq']}")
        old_tx_range = self.tx_range
        self.tx_range = self.distance(self.pos, SINK_POS)
        self.send(SINK_NODE, msg=msg, src=src, **kwargs)
        self.tx_range = old_tx_range

    ############################
    def calculate_chsv(self):
        # chsv = cluster head selection value
        chsv_point = self.pin
        sum_snr = 0

        for distance in self.neighbor_distance_list:
            if distance[0] <= self.tx_range:
                z = 7 * random.uniform(0, 1)
                b = -50 - 37.6 * math.log10(distance[0]) + z
                snr = b / 94
                self.log(snr)
                sum_snr += snr

        chsv_point *= sum_snr

        return chsv_point

    def distance(self, p0, p1):
        return math.sqrt((p0[0] - p1[0]) ** 2 + (p0[1] - p1[1]) ** 2)


###########################################################
sim = wsp.Simulator(
    until=50,
    timescale=10,
    visual=True,
    terrain_size=(700, 700),
    title="Cluster based demo")

# line style for member links
sim.scene.linestyle("CH", color=(0.5, 0.5, 0), width=0.5)
sim.scene.linestyle("GW", color=(1, 0, 1), width=2, arrow='both')
sim.scene.linestyle("SINK", color=(0, 1, 1), width=2, arrow='both')

nodes = {}

for x in range(6):
    for y in range(6):
        px = 60 + x * 100 + random.uniform(-40, 40)
        py = 60 + y * 100 + random.uniform(-40, 40)
        node = sim.add_node(MyNode, (px, py))
        node.max_range = 500
        node.min_range = 10
        node.tx_range = 150
        node.pin = random.uniform(700, 1000)
        node.logging = True

        nodes[node.id] = node

SINK_NODE = 36
SINK_POS = (610, 610)

sink_node = sim.add_node(MyNode, SINK_POS)
sink_node.tx_range = 150
sink_node.logging = True

sim.run()
