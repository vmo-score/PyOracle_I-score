import pyoracle
import random
import numpy as np
from Resources.PyOracle.PyOracle import get_distance

from matplotlib.mlab import find
from collections import defaultdict, deque

import pyext

import shelve

# used for sending messages from py to max
class DrawSendClass(pyext._class):
    def send(self, string = None, address = None):
        if address == None:
            self._send('to_draw', string)
        else:
            print address
            self._send(address, string)

features = 'mfcc', 'centroid', 'amp', 'zerocrossings', 'pitch', 'chroma'

# make individual oracles for each feature
mfcc_oracle = {'sfx': [], 'trn': [], 'rsfx': [], 'lrs': [], 'data': []}
centroid_oracle = {'sfx': [], 'trn': [], 'rsfx': [], 'lrs': [], 'data': []}
amp_oracle = {'sfx': [], 'trn': [], 'rsfx': [], 'lrs': [], 'data': []}
zerocross_oracle = {'sfx': [], 'trn': [], 'rsfx': [], 'lrs': [], 'data': []}
pitch_oracle = {'sfx': [], 'trn': [], 'rsfx': [], 'lrs': [], 'data': []}
chroma_oracle = {'sfx': [], 'trn': [], 'rsfx': [], 'lrs': [], 'data': []}

current_oracle = mfcc_oracle

section_oracle = {'sfx': [], 'trn': [], 'rsfx': [], 'lrs': [], 'data': []}
section_mfccs = []
section_frame_count = 0
section_frame_size = 4
section_sect = 1

# events list stores data for query
events_list = []
sections = []

oracle_number = 0

s = [1] # current point for nav
k = 1 # starting point for nav
p = 0.5 # jump probability

thresh = 0.1
thresholds = defaultdict(float)
sect_thresh = 1
query_thresh = 0.1

lrs = 0

weights = {'mfcc': 1.0,
           'centroid': 0.0,
           'amp': 0.0,
           'pitch': 0.0,
           'zerocrossings': 0.0}

region = {'start': 0.0, 'end': 1.0}
start = 0
end = 1
regions_active = 0
query_active = 0

# taboo list
taboo_len = 0
taboo_list = deque(maxlen = taboo_len)
taboo_active = False

send_class = DrawSendClass()


def load_thresholds(folder_path):
    global features, thresholds

    file = shelve.open(folder_path + "/thresholds.dat")
    thresholds = file['thresholds']
    file.close()

    for feature in features:
        address = 'ideal_t_' + feature
        send_class.send(thresholds[feature], address)


def load_oracle(folder_path):
    '''
    load oracles from given folder
    mfcc, centroid, amp, zerocross, pitch, chroma
    all .dat
    '''
    global mfcc_oracle, centroid_oracle, amp_oracle, zerocross_oracle, pitch_oracle, chroma_oracle, events_list
    folder_path = str(folder_path).split(':')[1]
    centroid_oracle = pyoracle.load_oracle(folder_path + 'centroid_oracle.dat.db')
    amp_oracle = pyoracle.load_oracle(folder_path + 'amp_oracle.dat.db')
    zerocross_oracle = pyoracle.load_oracle(folder_path + 'zerocross_oracle.dat.db')
    pitch_oracle = pyoracle.load_oracle(folder_path + 'pitch_oracle.dat.db')
    chroma_oracle = pyoracle.load_oracle(folder_path + 'chroma_oracle.dat.db')
    mfcc_oracle = pyoracle.load_oracle(folder_path + 'mfcc_oracle.dat.db')
    print chroma_oracle['sfx']
    print chroma_oracle['trn']
    print chroma_oracle['rsfx']
    print chroma_oracle['lrs']
    print "chroma oracle: ", chroma_oracle['data']
    events_list = chroma_oracle['data'][1:]


def save_thresholds(folder_path):
    global thresholds
    file = shelve.open(folder_path + "/thresholds.dat")
    file['thresholds'] = thresholds
    file.close()


def save_oracle(folder_path):
    '''
    save all oracles to a given folder
    each folder should be unique to a given recording
    all .dat
    '''
    global mfcc_oracle, centroid_oracle, amp_oracle, zerocross_oracle, pitch_oracle, chroma_oracle
    folder_path = str(folder_path).split(':')[1]
    pyoracle.save_oracle(mfcc_oracle, folder_path + '/mfcc_oracle.dat')
    pyoracle.save_oracle(centroid_oracle, folder_path + '/centroid_oracle.dat')
    pyoracle.save_oracle(amp_oracle, folder_path + '/amp_oracle.dat')
    pyoracle.save_oracle(zerocross_oracle, folder_path + '/zerocross_oracle.dat')
    pyoracle.save_oracle(pitch_oracle, folder_path + '/pitch_oracle.dat')
    pyoracle.save_oracle(chroma_oracle, folder_path + '/chroma_oracle.dat')

    save_thresholds(folder_path)


def set_taboo_active(n):
    global taboo_active
    if n == 0:
        taboo_active = False
    else:
        taboo_active = True

def set_taboo_length(n):
    global taboo_len, taboo_list
    taboo_len = n
    taboo_list = deque(maxlen = n)
    print 'changed taboo list length to', n

def set_region(s, e):
    global region, start, end, current_oracle
    region['start'] = s
    region['end'] = e
    start = int(len(current_oracle['lrs'])*region['start'])
    end = int(len(current_oracle['lrs'])*region['end'])
    if end <= start:
        end = start + 5

def toggle_regions(tog):
    global regions_active
    if tog == 0:
        regions_active = False
        print 'regions off'
    else:
        regions_active = True
        print 'regions on'

def set_threshold(feature, new_thresh):
    global thresholds
    thresholds[feature] = new_thresh

def set_sect_threshold(new_thresh):
    global sect_thresh
    sect_thresh = new_thresh

def toggle_query(active):
    global query_active
    if active == 0:
        query_active = False
        print 'query off'
    else:
        query_active = True
        print 'query on'

def set_query_thresh(t):
    global query_thresh
    query_thresh = t

def start_improv():
    global k, s, region
    s = [1]
    k = 1
    region = {'start': 0.0, 'end': 1.0}

def learn_thresholds():
    global events_list
    global features
    global send_class
    global thresholds
    ideal_thresholds = {}
    for feature in features:
        feature_vec = {feature: [e[feature] for e in events_list]}
        # print feature_vec
        ideal_thresholds[feature] = pyoracle.calculate_ideal_threshold((0.005, 0.3, 0.001), feature_vec, feature)
        ideal_thresholds[feature] = ideal_thresholds[feature][0][1]
        address = 'ideal_t_'+feature
        send_class.send(ideal_thresholds[feature], address)
    thresholds = ideal_thresholds

def start_oracle():
    global mfcc_oracle, centroid_oracle, amp_oracle, zerocross_oracle, pitch_oracle
    global chroma_oracle
    global current_oracle, oracle_number
    global k, s, region
    global section_frame_count, section_mfccs, section_oracle
    global events_list


    s = [1]
    k = 1

    mfcc_oracle = {'sfx': [], 'trn': [], 'rsfx': [], 'lrs': [], 'data': []}
    centroid_oracle = {'sfx': [], 'trn': [], 'rsfx': [], 'lrs': [], 'data': []}
    amp_oracle = {'sfx': [], 'trn': [], 'rsfx': [], 'lrs': [], 'data': []}
    zerocross_oracle = {'sfx': [], 'trn': [], 'rsfx': [], 'lrs': [], 'data': []}
    pitch_oracle = {'sfx': [], 'trn': [], 'rsfx': [], 'lrs': [], 'data': []}
    chroma_oracle = {'sfx': [], 'trn': [], 'rsfx': [], 'lrs': [], 'data': []}

    section_oracle = {'sfx': [], 'trn': [], 'rsfx': [], 'lrs': [], 'data': []}

    oracle_type(oracle_number)

    pyoracle.Resources.PyOracle.PyOracle.add_initial_state(mfcc_oracle)
    pyoracle.Resources.PyOracle.PyOracle.add_initial_state(centroid_oracle)
    pyoracle.Resources.PyOracle.PyOracle.add_initial_state(amp_oracle)
    pyoracle.Resources.PyOracle.PyOracle.add_initial_state(zerocross_oracle)
    pyoracle.Resources.PyOracle.PyOracle.add_initial_state(pitch_oracle)
    pyoracle.Resources.PyOracle.PyOracle.add_initial_state(chroma_oracle)

    pyoracle.Resources.PyOracle.PyOracle.add_initial_state(section_oracle)

    region = {'start': 0.0, 'end': 1.0}

    section_frame_count = 0
    section_mfccs = [0] * 10

    events_list = []


def begin():
    global current_oracle
    start_oracle()
    return "Oracle Initialized"

def add_new_state(m1, m2, m3, m4, m5, m6, m7, m8, m9, m10, cent, amp, zc, p, c1, c2, c3, c4, c5, c6, c7, c8, c9, c10, c11, c12, time):
    global mfcc_oracle, centroid_oracle, amp_oracle, zerocross_oracle, pitch_oracle, chroma_oracle
    global thresh, sect_thresh
    global section_mfccs, section_frame_count, section_frame_size, section_oracle
    global events_list
    global thresholds

    new_event = {}
    mfccs = []
    mfccs.append(m1)
    mfccs.append(m2)
    mfccs.append(m3)
    mfccs.append(m4)
    mfccs.append(m5)
    mfccs.append(m6)
    mfccs.append(m7)
    mfccs.append(m8)
    mfccs.append(m9)
    mfccs.append(m10)

    new_event['mfcc'] = mfccs
    new_event['time'] = time

    new_event['amp'] = amp
    new_event['zerocrossings'] = zc
    new_event['pitch'] = p
    new_event['centroid'] = cent

    chroma = []
    chroma.append(c1)
    chroma.append(c2)
    chroma.append(c3)
    chroma.append(c4)
    chroma.append(c5)
    chroma.append(c6)
    chroma.append(c7)
    chroma.append(c8)
    chroma.append(c9)
    chroma.append(c10)
    chroma.append(c11)
    chroma.append(c12)
    new_event['chroma'] = chroma

    events_list.append(new_event)
    try:
        # subtract previous onset from current to determine previous duration
        events_list[-2]['duration'] = time - events_list[-2]['time']
    except IndexError:
        pass

    weights = defaultdict(float)
    weights['mfcc'] = 1.0
    pyoracle.Resources.PyOracle.PyOracle.add_state(mfcc_oracle, new_event, thresholds['mfcc'], weights)

    weights = defaultdict(float)
    weights['amp'] = 1.0
    pyoracle.Resources.PyOracle.PyOracle.add_state(amp_oracle, new_event, thresholds['amp'], weights)

    weights = defaultdict(float)
    weights['pitch'] = 1.0
    pyoracle.Resources.PyOracle.PyOracle.add_state(pitch_oracle, new_event, thresholds['pitch'], weights)

    weights = defaultdict(float)
    weights['centroid'] = 1.0
    pyoracle.Resources.PyOracle.PyOracle.add_state(centroid_oracle, new_event, thresholds['centroid'], weights)

    weights = defaultdict(float)
    weights['zerocrossings'] = 1.0
    pyoracle.Resources.PyOracle.PyOracle.add_state(zerocross_oracle, new_event, thresholds['zerocrossings'], weights)

    weights = defaultdict(float)
    weights['chroma'] = 1.0
    pyoracle.Resources.PyOracle.PyOracle.add_state(chroma_oracle, new_event, thresholds['chroma'], weights)

    # sections
    '''
    for i, val in enumerate(mfccs):
        section_mfccs[i] += val

    section_frame_count += 1
    if section_frame_count == section_frame_size:
        for i, val in enumerate(mfccs):
            section_mfccs[i] /= section_frame_size
        section_event = defaultdict(float)
        section_event['mfcc'] = section_mfccs

        weights = defaultdict(float)
        weights['mfcc'] = 1

        pyoracle.Resources.PyOracle.PyOracle.add_state(section_oracle, section_event, sect_thresh, weights)
        section_frame_count = 0
        section_mfccs = [0.0] * 10
        # calculate_sections()

    '''
    return 'n_states', len(mfcc_oracle['lrs'])

def dump_oracle():
    global current_oracle
    print 'transitions:', str(current_oracle['trn'])
    print 'suffixes:', str(current_oracle['sfx'])
    print 'rev. suffixes:', str(current_oracle['rsfx'])
    print 'lrs:', str(current_oracle['lrs'])

def set_probability(new_p):
    global p
    p = new_p

def set_lrs(new_lrs):
    global lrs
    lrs = new_lrs

def get_ir():
    global current_oracle
    IR, code, compror = pyoracle.calculate_ir(current_oracle)
    return 'ir', float(sum(IR))

def calculate_sections():
    global section_oracle, sections
    IR, code, compror = pyoracle.calculate_ir(section_oracle)

    sections = []
    position = 0

    for block in code:
        # (start, duration, label)
        # was block + 1
        if block[0] == 0:
            dur = 1
        else:
            dur = block[0]
        sections.append((position, dur, block[1]))
        position += dur

    filtered_sections = []

    for i, sec in enumerate(sections):
        if i < len(sections) - 1 and sec[2] == sections[i+1][2]:
            new_sec = (sec[0], sec[1] + sections[i+1][1], sec[2])
            filtered_sections.append(new_sec)
            del sections[i+1]
        else:
            filtered_sections.append(sec)

    output = 'sections '

    for sec in filtered_sections:
        output += str(sec[0]) + ' '
        output += str(sec[1]) + ' '
        output += str(sec[2]) + ''
        output += ' foo '

    sections = filtered_sections

    return output


def oracle_type(n):
    global current_oracle, oracle_number
    print 'switched features: ', n
    oracle_number = n
    current_oracle = {0: mfcc_oracle,
                      1: centroid_oracle,
                      2: amp_oracle,
                      3: zerocross_oracle,
                      4: pitch_oracle,
                      5: chroma_oracle}[n]

def get_next_state():
    '''
    generate output state from audio oracle
    outputs:
        k - value of next state
    '''
    global s, k,p, lrs, start, end, regions_active, current_oracle
    global query_active, events_list, query_thresh
    global taboo_list, taboo_active
    global events_list

    ktrace = [1]
    in_region = False

    # these should be globals which are set elsewhere
    # so regions don't change dynamically with the oracle size
    # start = int(len(oracle)*region['start'])
    # end = int(len(oracle)*region['end'])

    # forward transition or jump
    oracle = current_oracle

    if (random.random() < p) and k < len(oracle['lrs']) - 1:
        # transition
        k += 1
    else:
        if query_active != True:
            print 'jump'
            # maybe look more into 'navigating the oracle paper'
            # suffix
            try:
                options = [oracle['sfx'][k] + 1]
            except:
                options = [1]
            # rev sfx
            rsfxs = oracle['rsfx'][k]
            rsfxs = [rsfx + 1 for rsfx in rsfxs if rsfx != k + 1]
            options.append(oracle['rsfx'][k])
            # suffix of suffix
            try:
                # fix so we jump to transition FROM suffix
                options.append(oracle['sfx'][oracle['sfx'][k]] + 1)
            except:
                # if zero
                options.append(0)
            # rsfx of rsfx
            if type(oracle['rsfx'][k]) == int:
                # single val
                if oracle['rsfx'][oracle['rsfx'][k]] != k + 1:
                    options.append(oracle['rsfx'][oracle['rsfx'][k]] + 1)
            else:
                # list
                vals = [oracle['rsfx'][rs] for rs in oracle['rsfx'][k] if rs != k+1]
                flat_vals = []
                for v in vals:
                    if type(v) == list:
                        for n in v:
                            flat_vals.append(n)
                    else:
                        flat_vals.append(v)
                options.append(flat_vals)

            flat_options = []
            for item in options:
                if type(item) == int:
                    flat_options.append(item)
                else:
                    try:
                        for sub_item in item:
                            flat_options.append(sub_item)
                    except:
                        pass
            options = flat_options
            # options = filter(lambda x: type(x) == int, options)

            options = filter(lambda x: x != k + 1, options)
            options = filter(lambda x: oracle['lrs'][x] >= lrs, options)
            try:
                # k = sorted(options, key = lambda x: oracle['lrs'][x])[-1]
                in_taboo = True
                iteration_limit = 10
                num_iterations = 0
                while in_taboo and num_iterations < iteration_limit:
                    num_iterations += 1
                    k = random.choice(options)
                    # but if we jump back to zero, choose a new state
                    if k == 0:
                        k = random.choice(oracle['trn'][0])
                    if k not in taboo_list:
                        in_taboo = False
                        break
                # if still cant find one, then choose randomly
                else:
                    print 'failed'
                    k = random.choice(oracle['trn'][0])

            except:
                # if no good jump, then step forward
                print 'failed to find good jump'
                k += 1
        else:
            # query and stuff
            # just using mfccs for now, but will eventually switch feats

            # this is too much
            # need to limit this somehow
            # probably just look at suffixes and transitions from current state
            # and attached states
            # choose nearest
            # and make a path there
            print 'query jump'
            path = follow_path(current_oracle, k)
            # print path
            k = path
            # print 'k'



    # if k is out of region
    num_iterations = 0
    iteration_limit = 40
    while ((start > k or k > end) and regions_active) or (taboo_active and k in taboo_list):
        if num_iterations > iteration_limit:
            print 'reached max iterations'
            k = random.choice(range(start, end))
            return 'next_state', k
        num_iterations += 1
        print 'out of region or in taboo list'
        # do another suffix jump
        options = [oracle['sfx'][k]]
        # rev sfx
        options.append(oracle['rsfx'][k])
        # suffix of suffix
        options.append(oracle['sfx'][oracle['sfx'][k]])
        # rsfx of rsfx
        # print k
        # options.append([oracle['rsfx'][rs] for rs in oracle['rsfx'][k]])

        options = filter(lambda x: type(x) == int, options)
        for opt in options:
            if start <= opt <= end:
                k = opt
                return 'next_state', k
        # if no good option found, jump back along suffix
        # could also jump forward if we're behind the region
        k = oracle['sfx'][k]
        if k == 0:
            k = random.choice(oracle['trn'][0])

    taboo_list.append(k)

    return 'next_state', k, events_list[k]['time'], events_list[k]['duration']

def choose_section():
    ''' driven externally from max/msp '''
    global region, start, end, current_oracle, section_oracle, sections

    sect_p = 0.15
    if random.random() < sect_p:
        # choose new section
        # new section is (start frame, duration, label)
        # weighted random favoring long sections
        sorted_sections = sorted(sections, key = lambda x: x[1], reverse = True)
        r_num_1 = random.randint(0, len(sorted_sections) - 1)
        r_num_2 = random.randint(0, len(sorted_sections) - 1)
        # new_section = random.choice(sections)
        new_section = sorted_sections[min(r_num_2, r_num_1)]

        s = float(new_section[0]) / len(section_oracle['lrs'])
        e = s + (float(new_section[1]) / len(section_oracle['lrs']))

        # handle region constraints
        region['start'] = s
        region['end'] = e
        start = int(len(current_oracle['lrs'])*region['start'])
        end = int(len(current_oracle['lrs'])*region['end'])
        if end <= start:
            end = start + 5
        return 'to_region_slider', s, e

def follow_path(oracle, current):
    global query_thresh, events_list
    input_vector = events_list[-1]

    forward_limit = 5 # number of forward steps allowed after suffix

    # just mfccs for now
    weights = defaultdict(float)
    weights['chroma'] = 1.0

    max_num_possibilities = 20
    possibilities = []

    for i, past_event in enumerate(events_list):
        if get_distance(past_event, input_vector, weights) <= query_thresh:
            possibilities.append(i)
        if len(possibilities) >= max_num_possibilities:
            break

    # now we have list of possibilities - states which are similar
    # gather states collected to current by suffixes or rev suffixes
    connected_states = []
    k = current
    # backtrack along suffixes
    while k != None:
        # add suffixes
        try:
            connected_states.append(oracle['sfx'][k] + 1)
        except TypeError:
            # nonetype
            pass
        # add rev suffixes
        if type(oracle['rsfx'][k]) == list:
            a = list(np.array(oracle['rsfx'][k]) + 1)
            connected_states.extend(a)
        else:
            connected_states.append(oracle['rsfx'][k] + 1)
        # add transitions
        if type(oracle['trn'][k]) == list:
            connected_states.extend(oracle['trn'][k])
        else:
            connected_states.append(oracle['trn'][k])
        k = oracle['sfx'][k]

    connected_states = set(connected_states)
    # in this case, choose the earliest state that matches
    # but we probably want to choose the closest or highest LRS
    # sort possibilities according to distance from input_vector
    # possibilities = sorted(possibilities, key = lambda x: get_distance(events_list[x], input_vector, weights))
    random.shuffle(possibilities)
    print possibilities, connected_states
    for pos in possibilities:
        # check if pos is temporaly too close to current input
        follow_limit = 2
        if pos >= len(events_list) - follow_limit:
            break
        if pos in connected_states:
            return pos

    return current + 1

def draw_oracle():
    global current_oracle, k, send_class
    lrs_threshold = 0 # placeholder for now...
    oracle = current_oracle
    width, height = 571, 103
    N_states = len(oracle['sfx'])

    send_class.send('clear')
    send_class.send('brgb 0 0 0') # set background to black
    send_class.send('frgb 255 255 255') # set pen to white

    send_class.send('linesegment 0 51 571 51')

    increment = 1
    '''
    if N_states > 50:
        increment = int(N_states / 25)

    '''
    for i in range(0, N_states, increment):
        x_pos = (float(i) / N_states * width) + 0.5 * 1.0 / N_states * width
        # iterate over forward transitions
        for tran in oracle['trn'][i]:
            # if forward transition to next state
            if tran == i + 1:
                pass
                # draw forward transitions
                '''
                next_x = (float(i + increment) / N_states * width) + 0.5 * 1.0 / N_states * width
                current_x = x_pos + (0.25 / N_states * width)
                send_class.send('linesegment %f %f %f %f' % (current_x, height/2, next_x, height/2))
                '''
            else:
                # forward transition to another state
                current_x = x_pos
                next_x = (float(tran) / N_states * width) + (0.5 / N_states * width)
                arc_height = (height / 2) + (tran - i) * 0.125
                send_class.send('framearc %f %f %f %f %f %f' % (current_x, height/2 - arc_height / 2,
                                next_x, height/2 + arc_height/2, 270, 180))
            if oracle['sfx'][i] is not None and oracle['sfx'][i] != 0 and oracle['lrs'][oracle['sfx'][i]] >= lrs_threshold:
                current_x = x_pos
                next_x = (float(oracle['sfx'][i]) / N_states * width) + (0.5 / N_states * width)
                # draw arc
                arc_height = (height / 2) - (oracle['sfx'][i] - i) * 0.125
                send_class.send('framearc %f %f %f %f %f %f' % (next_x,
                                                                height/2 - arc_height/2,
                                                                current_x,
                                                                height/2 + arc_height/2,
                                                                90,
                                                                180))
    '''
    for i in range(0, N_states, increment):
        color = 255, 255, 255
        if i == k:
            color = 255, 0, 0
        x_pos = (float(i) / N_states * width) + 0.5 * 1.0 / N_states * width
        circle_width = (0.5 / (N_states / increment) * width) / 2
        send_class.send('paintoval %f %f %f %f %f %f %f' % (x_pos - circle_width,
                                                   height/2 - circle_width,
                                                   x_pos+circle_width,
                                                   height/2 + circle_width,
                                                   color[0], color[1], color[2]))
    '''











































































