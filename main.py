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
    Node_Residual_Msg = 1
    I_am_Cluster_Head = 2
    I_am_Cluster_Member = 3
    Cluster_Head_Residual_Msg = 4


###########################################################
class MyNode(wsp.Node):
    tx_range = 100

    ###################
    def init(self):
        super().init()
        self.status = Status.UNDEFINED
        self.chsv_neighbors = {}
        self.psv_neighbors = {}
        self.chsv_point = 1000
        self.psv_point = 1000
        self.pin = 1000
        self.parent = None
        ############
        # for member
        self.cluster_heads = []
        self.cluster_head_official = None
        # for cluster head
        self.psv_neighbors = {}
        self.members = []
        self.cluster_adjacency = {}

    ###################
    def run(self):
        if self.id is SINK_NODE:
            self.scene.nodecolor(self.id, 0, 0, 0)
            self.scene.nodewidth(self.id, 2)
        else:
            self.scene.nodecolor(self.id, 0.7, 0.7, 0.7)
            self.sim.env.process(self.setup_phase())

    ###################
    def setup_phase(self):
        self.chsv_point = self.calculate_chsv()
        yield self.timeout(BROADCAST_DELAY)
        self.send(wsp.BROADCAST_ADDR, msg=Message.Node_Residual_Msg, src=self.id, chsv=self.chsv_point)

        yield self.timeout(.2)

        if len(self.chsv_neighbors) == 0 or self.chsv_point >= max(self.chsv_neighbors.values()):
            self.switch_state(Status.CLUSTER_HEAD)
            yield self.timeout(BROADCAST_DELAY)
            self.send(wsp.BROADCAST_ADDR, msg=Message.I_am_Cluster_Head, src=self.id)

        yield self.timeout(.5)

        yield self.sim.env.process(self.steady_phase())


    def steady_phase(self):
        if self.status == Status.MEMBER:
            # self.scene.clearlinks()
            seq = 0
            yield self.timeout(BROADCAST_DELAY)
            self.send(wsp.BROADCAST_ADDR, msg="My cluster heads", src=self.id, cluster_heads=self.cluster_heads)
            self.log(f"Cluster head: {self.cluster_heads}")
            while True:
                yield self.timeout(BROADCAST_DELAY + random.uniform(0.1, 0.7))
                # self.log(f"Send data to {SINK_NODE} (via {self.cluster_head_official}) - seq {seq}")
                self.send(self.cluster_head_official, msg='Data', src=self.id, seq=seq)
                seq += 1

        elif self.status == Status.CLUSTER_HEAD:
            seq = 0
            self.data_combine = ''
            yield self.timeout(0.5)

            self.psv_point = self.calculate_psv()
            self.psv_neighbors = {}

            for node in self.cluster_adjacency.keys():
                self.timeout(BROADCAST_DELAY)
                self.send_to_cluster_adjacency(msg=Message.Cluster_Head_Residual_Msg, src=self.id, chdest=node, psv_point=self.psv_point)

            yield self.timeout(.5)

            if len(self.psv_neighbors) > 0:
                max_psv = max(self.psv_neighbors.values())
                if self.psv_point >= max_psv:
                    self.parent = SINK_NODE
                else:
                    for id in self.psv_neighbors.keys():
                        if self.psv_neighbors[id] == max_psv:
                            self.parent = id
                            break
            else:
                self.parent = SINK_NODE


            while True:
                seq += 1
                if self.parent != SINK_NODE:
                    self.timeout(BROADCAST_DELAY + random.uniform(0.1, 0.4))
                    self.send_to_cluster_adjacency(msg='Data_Combine', chdest=self.parent, src=self.id, seq=seq, data=self.data_combine)
                else:
                    yield self.timeout(BROADCAST_DELAY + .5)
                    self.send_data_to_sink(msg="Data_Combine", src=self.id, seq=seq, data=self.data_combine)

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

        elif self.status is Status.CLUSTER_HEAD:
            if msg == Message.I_am_Cluster_Member:
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
            elif msg == Message.Cluster_Head_Residual_Msg:
                self.psv_neighbors[src] = kwargs["psv_point"]
            elif msg == "Data":
                seq = kwargs['seq']
                self.data_combine += f'\nSource {src}: seq {seq}'
            elif msg == "Data_Combine":
                self.data_combine += f'\nData from Cluster {src}: \n{kwargs["data"]}'
                if self.parent != SINK_NODE:
                    self.timeout(BROADCAST_DELAY)
                    self.send_to_cluster_adjacency(msg='Data_Combine', chdest=self.parent, src=self.id, data=self.data_combine)
                    self.data_combine = ""
        elif self.status is Status.MEMBER:
            if msg == Message.I_am_Cluster_Head:
                self.cluster_heads.append(src)
            elif msg == Message.Cluster_Head_Residual_Msg:
                dest = kwargs["chdest"]
                yield self.timeout(BROADCAST_DELAY)
                self.send(dest, msg=msg, src=src, **kwargs)
            elif msg == "Data_Combine":
                dest = kwargs["chdest"]
                yield self.timeout(BROADCAST_DELAY)
                self.send(dest, msg=msg, src=src, **kwargs)

        elif self.status is Status.UNDEFINED:
            if msg == Message.Node_Residual_Msg:
                self.chsv_neighbors[src] = kwargs['chsv']
            elif msg == Message.I_am_Cluster_Head:
                self.switch_state(Status.MEMBER)
                self.cluster_heads.append(src)
                self.cluster_head_official = src
                yield self.timeout(BROADCAST_DELAY)
                self.send(wsp.BROADCAST_ADDR, msg=Message.I_am_Cluster_Member, src=self.id,
                          cluster_head=self.cluster_head_official)
            elif msg == Message.I_am_Cluster_Member:
                if sender in self.chsv_neighbors:
                    del self.chsv_neighbors[sender]

                if len(self.chsv_neighbors) == 0 or self.chsv_point >= max(self.chsv_neighbors.values()):
                    self.switch_state(Status.CLUSTER_HEAD)
                    # self.log(f'Start broadcast CH message')
                    yield self.timeout(BROADCAST_DELAY)
                    self.send(wsp.BROADCAST_ADDR, msg=Message.I_am_Cluster_Head, src=self.id)
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
        sum_distance = 0

        for distance in self.neighbor_distance_list:
            if distance[0] <= self.tx_range:
                sum_distance += distance[0] ** 2

        if sum_distance != 0:
            chsv_point = self.pin/math.sqrt(sum_distance)

        return chsv_point

    def calculate_psv(self):
        # psv = parent selection value

        cluster_adjacencies = self.cluster_adjacency.keys()
        denominator = 0

        for node in self.neighbor_distance_list:
            if node[1].id in cluster_adjacencies:
                denominator += node[1].pin/node[0]

        if denominator == 0:
            return self.pin
        else:
            return self.pin/denominator

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

nodes = {}

for x in range(6):
    for y in range(6):
        px = 60 + x*100 + random.uniform(-40, 40)
        py = 60 + y*100 + random.uniform(-40, 40)
        node = sim.add_node(MyNode, (px, py))
        node.max_range = 500
        node.min_range = 10
        node.tx_range = 150
        node.logging = True

        nodes[node.id] = node

SINK_NODE = 36
SINK_POS = (680, 680)

sink_node = sim.add_node(MyNode, SINK_POS)
sink_node.tx_range = 0
sink_node.logging = True

sim.run()
