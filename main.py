import math
import random
import wsnsimpy.wsnsimpy_tk as wsp
import enum

class Status(enum.Enum):
    UNDEFINED = 0
    MEMBER = 1
    CLUSTER_HEAD = 2

###########################################################
def delay():
    return random.uniform(.2,.8)

###########################################################
class MyNode(wsp.Node):
    tx_range = 100

    ###################
    def init(self):
        super().init()
        self.prev = None
        self.status = Status.UNDEFINED
        self.chsv_neighbors = []
        self.chsv_point = 1000
        self.pin = 1000
        ############
        self.cluster_head = None
        self.members = None

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
        self.boardcast_chsv()

        yield self.timeout(1)

        if len(self.chsv_neighbors) == 0 or self.chsv_point >= max(self.chsv_neighbors):
            self.sim.env.process(self.switch_state(Status.CLUSTER_HEAD))

        yield self.timeout(1)
        self.sim.env.process(self.steady_phase())

    def steady_phase(self):
        if self.status == Status.MEMBER:
            # self.scene.clearlinks()
            seq = 0
            while True:
                self.send_data_to_CH(self.id, seq)
                seq += 1
                yield self.timeout(1)

    ###################

    def switch_state(self, status: Status):
        if status == Status.CLUSTER_HEAD:
            self.log(f'Set status to Cluster Head')
            self.status = Status.CLUSTER_HEAD
            self.tx_range = 190
            self.members = []
            self.scene.nodecolor(self.id, 0, 1, 0)
            self.scene.nodewidth(self.id, 2)
            self.boardcast_CH()
            yield self.timeout(1)
        elif status == Status.MEMBER:
            self.log(f'Set status to Member')
            self.status = Status.MEMBER
            self.tx_range = 190
            self.scene.nodecolor(self.id, 1, 0, 0)
            self.scene.nodewidth(self.id, 2)
            yield self.timeout(0)


    ###################
    def boardcast_chsv(self):
        chsv_point = self.calculate_chsv()
        self.send(wsp.BROADCAST_ADDR, msg='hello', src=self.id, chsv=chsv_point)

    def calculate_chsv(self):
        sum_distance = 0

        for distance in self.neighbor_distance_list:
            if distance[0] <= self.tx_range:
                sum_distance += distance[0] ** 2

        if sum_distance != 0:
            self.chsv_point = self.pin/sum_distance
        else:
            self.chsv_point = self.pin

        self.log(f'CHSV point of {self.id} is {self.chsv_point}')
        return self.chsv_point

    def boardcast_CH(self):
        self.log(f'Start boardcast CH message')
        self.send(wsp.BROADCAST_ADDR, msg='CH', src=self.id)

    def send_CH_ack(self):
        self.send(self.cluster_head, msg='CH_ACK', src=self.id)

    ###################
    def send_data_to_CH(self, src, seq):
        self.log(f"Send data to {SINK_NODE} (via {self.cluster_head}) - seq {seq}")
        self.send(self.cluster_head, msg='data', src=src, seq=seq)

    def send_data_to_sink(self, msg, src, seq):
        self.log(f"Forward data from {src} to {SINK_NODE} - seq {seq}")
        old_tx_range = self.tx_range
        self.tx_range = self.distance(self.pos, SINK_POS)
        self.send(SINK_NODE, msg=msg, src=src, seq=seq)
        self.tx_range = old_tx_range

    ###################
    def on_receive(self, sender, msg, src, **kwargs):

        if msg == 'hello' and self.id != SINK_NODE:
            self.log(f'Receive CHSV message from {src}, chsv: {kwargs["chsv"]}')
            self.chsv_neighbors.append(kwargs['chsv'])

        elif msg == 'CH' and self.id != SINK_NODE:
            self.log(f'Receive CH message from {src}')
            if self.status == Status.UNDEFINED:
                self.sim.env.process(self.switch_state(Status.MEMBER))
                self.cluster_head = src
                yield self.timeout(0.2)
                self.send_CH_ack()
                self.scene.addlink(sender, self.id, "CH")

        elif msg == 'CH_ACK' and self.id != SINK_NODE:
            self.log(f'Receive CH ACK message from {src}')
            if self.status == Status.CLUSTER_HEAD:
                self.members.append(src)

        elif msg == 'data':
            if self.status == Status.CLUSTER_HEAD:
                yield self.timeout(.2)
                self.send_data_to_sink(msg, src, kwargs['seq'])
            elif self.id == SINK_NODE:
                seq = kwargs['seq']
                self.log(f"Got data from {sender} (source: {src}) - seq {seq}")

    def distance(self, p0, p1):
        return math.sqrt((p0[0] - p1[0]) ** 2 + (p0[1] - p1[1]) ** 2)
###########################################################
sim = wsp.Simulator(
        until=100,
        timescale=1,
        visual=True,
        terrain_size=(700,700),
        title="Cluster based demo")

# line style for member links
sim.scene.linestyle("CH", color=(0,.8,0), arrow="tail", width=2)

for x in range(6):
    for y in range(6):
        px = 50 + x*100 + random.uniform(-40, 40)
        py = 50 + y*100 + random.uniform(-40, 40)
        node = sim.add_node(MyNode, (px, py))
        node.tx_range = 150
        node.logging = True

SINK_NODE = 36
SINK_POS = (680, 680)

sink_node = sim.add_node(MyNode, SINK_POS)
sink_node.tx_range = 0
sink_node.logging = True

sim.run()
