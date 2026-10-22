"""Named common-task action port, not an author checkpoint or controller.

Original positive additive25..300 shunts are encoded as absolute total-stock
targets. This makes the action idempotent, as required by the published
unique-actions DQN rule. No generator/PV capability is silently added.
"""
from dataclasses import dataclass
Q=(25,50,75,100,125,150,200,250,300)
TARGETS=tuple(range(25,451,25))


@dataclass(frozen=True)
class AbsoluteShuntRole:
    buses: tuple

    def __post_init__(self):
        assert self.buses and tuple(sorted(set(self.buses)))==self.buses
        assert all(type(b) is int and b>=0 for b in self.buses)

    @property
    def size(self):return 1+len(self.buses)*len(TARGETS)

    def encode(self,bus,target):
        assert bus in self.buses and target in TARGETS
        return 1+self.buses.index(bus)*len(TARGETS)+TARGETS.index(target)

    def decode(self,index):
        assert type(index) is int and 1<=index<self.size
        b,q=divmod(index-1,len(TARGETS));return self.buses[b],TARGETS[q]

    def native_delta(self,index,current_stock,allowed_buses,already_used=()):
        if index==0:return None  # Explicit stop, never a fabricated action.
        assert index not in already_used,'Idempotent target already used in episode'
        bus,target=self.decode(index);assert bus in allowed_buses
        current=float(current_stock[bus]);assert 0<=current<=450 and current%25==0
        delta=target-current;assert delta in Q and current+delta<=450
        return {'add_shunts_q_mvar':{str(bus):float(delta)}}

    def mask(self,current_stock,allowed_buses,already_used=()):
        allowed=set(allowed_buses);used=set(already_used);mask=[False]*self.size;mask[0]=True
        for bus in self.buses:
            current=float(current_stock[bus]);assert 0<=current<=450 and current%25==0
            if bus not in allowed:continue
            for delta in Q:
                target=current+delta
                if target<=450:
                    action=self.encode(bus,int(target))
                    if action not in used:mask[action]=True
        return mask
