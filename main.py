import math
import random
import wsnsimpy.wsnsimpy_tk as wsp
import enum

BROADCAST_DELAY = .1

class Status(enum.Enum):
    UNDEFINED = 0
    MEMBER = 1
    CLUSTER_HEAD = 2

###########################################################
class MyNode(wsp.Node):
    tx_range = 100

    ###################
    def init(self):
        super().init()
        self.status = Status.UNDEFINED
        self.chsv_neighbors = {}
        self.chsv_point = 1000
        self.pin = 1000
        ############
        self.cluster_heads = None
        self.cluster_head_official = None
        self.members = None

    def reset(self):
        self.status = Status.UNDEFINED
        self.chsv_neighbors = {}
        self.chsv_point = 1000
        self.cluster_heads = []
        self.cluster_head_official = None
        self.members = []
        self.cluster_neighbors = {}

    ###################
    def run(self):
        if self.id is SINK_NODE:
            self.scene.nodecolor(self.id, 0, 0, 0)
            self.scene.nodewidth(self.id, 2)
        else:
            # self.reset()
            self.scene.nodecolor(self.id, 0.7, 0.7, 0.7)
            self.sim.env.process(self.setup_phase())

    ###################
    def setup_phase(self):
        self.chsv_point = self.calculate_chsv()
        yield self.timeout(BROADCAST_DELAY)
        self.send(wsp.BROADCAST_ADDR, msg='Hello', src=self.id, chsv=self.chsv_point)

        yield self.timeout(.5)

        if len(self.chsv_neighbors) == 0 or self.chsv_point >= max(self.chsv_neighbors.values()):
            self.switch_state(Status.CLUSTER_HEAD)
            self.log(f'Start broadcast CH message')
            yield self.timeout(BROADCAST_DELAY)
            self.send(wsp.BROADCAST_ADDR, msg='I am Cluster Head', src=self.id)

        yield self.timeout(.5)

        self.sim.env.process(self.steady_phase())


    def steady_phase(self):
        if self.status == Status.MEMBER:
            # self.scene.clearlinks()
            seq = 0
            yield self.timeout(BROADCAST_DELAY)
            self.send(wsp.BROADCAST_ADDR, msg="My cluster heads", src=self.id, cluster_heads=self.cluster_heads)
            self.log(f"Cluster head: {self.cluster_heads}")
            while seq < 2:
                yield self.timeout(BROADCAST_DELAY + random.uniform(0.1, 0.7))
                # self.log(f"Send data to {SINK_NODE} (via {self.cluster_head_official}) - seq {seq}")
                # self.send(self.cluster_head_official, msg='Data', src=self.id, seq=seq)
                seq += 1

        elif self.status == Status.CLUSTER_HEAD:
            seq = 0
            self.data_combine = ''
            yield self.timeout(2)
            # self.send_data_to_sink(msg='Data', src=self.id, seq=seq, data=self.data_combine)
            seq += 1
            self.log(f"Members: {self.members}\nCluster neighbors: {self.cluster_neighbors}")

            # self.send_data_to_sink(msg='Cluster information', src=self.id, seq=seq, data=self.members)
        # elif self.status == Status.UNDEFINED:
        #     # self.log('Status undefined -> Self-promoted to Cluster head')
        #     self.switch_state(Status.CLUSTER_HEAD)
        #     self.sim.env.process(self.steady_phase())

    ###################
    def on_receive(self, sender, msg, src, **kwargs):

        if msg == 'Hello' and self.status == Status.UNDEFINED and self.id != SINK_NODE:
            self.log(f'Receive CHSV message from {src}, chsv: {kwargs["chsv"]}')
            self.chsv_neighbors[src] = kwargs['chsv']

        elif msg == 'I am Cluster Head' and self.id != SINK_NODE:
            if self.status == Status.UNDEFINED:
                self.switch_state(Status.MEMBER)
                self.cluster_heads.append(src)
                self.cluster_head_official = src
                yield self.timeout(BROADCAST_DELAY)
                self.send(wsp.BROADCAST_ADDR, msg='I am Cluster Member', src=self.id, cluster_head=self.cluster_head_official)
            elif self.status == Status.MEMBER:
                self.cluster_heads.append(src)

        elif msg == 'I am Cluster Member' and self.id != SINK_NODE:
            if self.status == Status.CLUSTER_HEAD:
                if self.id == kwargs['cluster_head']:
                    self.members.append(src)
                    self.scene.addlink(sender, self.id, "CH")
            elif self.status == Status.UNDEFINED:
                if sender in self.chsv_neighbors:
                    del self.chsv_neighbors[sender]

                if len(self.chsv_neighbors) == 0 or self.chsv_point >= max(self.chsv_neighbors.values()):
                    self.switch_state(Status.CLUSTER_HEAD)
                    # self.log(f'Start broadcast CH message')
                    yield self.timeout(BROADCAST_DELAY)
                    self.send(wsp.BROADCAST_ADDR, msg='I am Cluster Head', src=self.id)
        elif msg == "My cluster heads" and self.id != SINK_NODE:
            if self.status == Status.CLUSTER_HEAD:
                heads = kwargs['cluster_heads']
                for h in heads:
                    if h != self.id:
                        if h in self.cluster_neighbors:
                            self.cluster_neighbors[h].append(src)
                        else:
                            self.cluster_neighbors[h] = [src]
                        self.scene.addlink(h, src, "GW")
        elif msg == 'Data':
            if self.status == Status.CLUSTER_HEAD:
                seq = kwargs['seq']
                self.data_combine += f'\nSource {src}: seq {seq}'
            elif self.id == SINK_NODE:
                seq = kwargs['seq']
                data = kwargs['data']
                self.log(f"Got data from {sender} (source: {src}) - seq {seq}: {data}")

        elif msg == 'Cluster information':
            self.log(f'Receive from {sender}: {kwargs["data"]}')

    ###################
    def switch_state(self, status: Status):
        if status == Status.CLUSTER_HEAD:
            # self.log(f'Set status to Cluster Head')
            self.status = Status.CLUSTER_HEAD
            self.members = []
            self.cluster_neighbors = {}
            self.scene.nodecolor(self.id, 0, 1, 0)
            self.scene.nodewidth(self.id, 2)
            self.scene.circle(
                self.pos[0], self.pos[1],
                self.tx_range)
        elif status == Status.MEMBER:
            # self.log(f'Set status to Member')
            self.status = Status.MEMBER
            self.cluster_heads = []
            self.scene.nodecolor(self.id, 1, 0, 0)
            self.scene.nodewidth(self.id, 2)

    ###################
    def send_data_to_sink(self, msg, src, **kwargs):
        # self.log(f"Forward data from {src} to {SINK_NODE} - seq {kwargs['seq']}")
        old_tx_range = self.tx_range
        self.tx_range = self.distance(self.pos, SINK_POS)
        self.send(SINK_NODE, msg=msg, src=src, **kwargs)
        self.tx_range = old_tx_range

    ############################
    def calculate_chsv(self):
        chsv_point = self.pin
        sum_distance = 0

        for distance in self.neighbor_distance_list:
            if distance[0] <= self.tx_range:
                sum_distance += distance[0] ** 2

        if sum_distance != 0:
            chsv_point = self.pin/math.sqrt(sum_distance)

        return chsv_point

    def distance(self, p0, p1):
        return math.sqrt((p0[0] - p1[0]) ** 2 + (p0[1] - p1[1]) ** 2)
###########################################################
sim = wsp.Simulator(
        until=50,
        timescale=3,
        visual=True,
        terrain_size=(700, 700),
        title="Cluster based demo")

# line style for member links
sim.scene.linestyle("CH", color=(0.5, 0.5, 0), width=0.5)
sim.scene.linestyle("GW", color=(1, 0, 1), width=2)

for x in range(6):
    for y in range(6):
        px = 60 + x*100 + random.uniform(-40, 40)
        py = 60 + y*100 + random.uniform(-40, 40)
        node = sim.add_node(MyNode, (px, py))
        node.max_range = 500
        node.min_range = 10
        node.tx_range = 130

        node.logging = True

SINK_NODE = 36
SINK_POS = (620, 620)

sink_node = sim.add_node(MyNode, SINK_POS)
sink_node.tx_range = 0
sink_node.logging = True

sim.run()
