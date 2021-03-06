"""
RawIO Class for NIX files

The RawIO assumes all segments and all blocks have the same structure.
It supports all kinds of NEO objects.

Author: Chek Yin Choi
"""

from __future__ import print_function, division, absolute_import
from neo.rawio.baserawio import (BaseRawIO, _signal_channel_dtype,
                                 _unit_channel_dtype, _event_channel_dtype)
import numpy as np
import warnings, traceback
try:
    import nixio as nix

    HAVE_NIX = True
except ImportError:
    HAVE_NIX = False
    nix = None


class NIXRawIO(BaseRawIO):

    extensions = ['nix']
    rawmode = 'one-file'

    def __init__(self, filename=''):
        BaseRawIO.__init__(self)
        self.filename = filename

    def _source_name(self):
        return self.filename

    def _parse_header(self):

        self.file = nix.File.open(self.filename, nix.FileMode.ReadOnly)
        sig_channels = []
        size_list = []
        for bl in self.file.blocks:
            for seg_index, _ in enumerate(bl.groups):
                seg = bl.groups[seg_index]
                for da_idx, da in enumerate(seg.data_arrays):
                    if da.type == "neo.analogsignal":
                        chan_id = da_idx
                        true_da = seg.data_arrays[chan_id]
                        #  true_da = da
                        try:
                            da_source = [
                                i for i in true_da.sources
                                if i.type == 'neo.channelindex'
                                ][0]
                            ch_name = da_source.metadata['neo_name']
                        except Exception:
                            traceback.print_exc()
                            ch_name = true_da.metadata['neo_name']
                        #  ch_name = da.metadata['neo_name']
                        #  
                        units = str(true_da.unit)
                        dtype = str(true_da.dtype)
                        sr = 1 / true_da.dimensions[0].sampling_interval
                        da_leng = true_da.size
                        if da_leng not in size_list:
                            size_list.append(da_leng)
                        group_id = 0
                        for sid, li_leng in enumerate(size_list):
                            if li_leng == da_leng:
                                group_id = sid
                                # very important! group_id use to store channel groups!!!
                                # use only for different signal length
                        gain = 1
                        offset = 0.
                        sig_channels.append((ch_name, chan_id, sr, dtype,
                                            units, gain, offset, group_id))
                break
            break
        sig_channels = np.array(sig_channels, dtype=_signal_channel_dtype)

        unit_channels = []
        unit_name = ""
        unit_id = ""
        for bl in self.file.blocks:
            for seg_index, _ in enumerate(bl.groups):
                seg = bl.groups[seg_index]
                mt_list = seg.multi_tags
                for mt_idx, mt in enumerate(mt_list):
                    true_mt = mt_list[mt_idx]
                    if true_mt.type == "neo.spiketrain":
                        try:
                            mt_source = [
                                i for i in true_mt.sources
                                if i.type == 'neo.unit'
                            ][0]
                            unit_name = mt_source.metadata['neo_name']
                            unit_id = mt_source.id
                        except Exception:
                            traceback.print_exc()
                            unit_name = true_mt.metadata['neo_name']
                            print('Error during loading {}'.format(unit_name))
                            unit_id = true_mt.id
                        #  unit_name = true_mt.metadata['neo_name']
                        #  unit_id =id
                        #  
                        if true_mt.features:
                            wf_units = true_mt.features[0].data.unit
                            wf_sampling_rate = 1 / true_mt.features[0].data.dimensions[
                                2].sampling_interval
                        else:
                            wf_units = None
                            wf_sampling_rate = 0
                        wf_gain = 1
                        wf_offset = 0.
                        if true_mt.features and "left_sweep" in true_mt.features[0].data.metadata:
                            wf_left_sweep = true_mt.features[0].data.metadata["left_sweep"] * wf_sampling_rate
                        else:
                            wf_left_sweep = 0
                        unit_channels.append((unit_name, unit_id, wf_units, wf_gain,
                                              wf_offset, wf_left_sweep, wf_sampling_rate))
                break
            break
        unit_channels = np.array(unit_channels, dtype=_unit_channel_dtype)

        event_channels = []
        event_count = 0
        epoch_count = 0
        for bl in self.file.blocks:
            for seg_index, _ in enumerate(bl.groups):
                seg = bl.groups[seg_index]
                mt_list = seg.multi_tags
                for mt_idx, mt in enumerate(mt_list):
                    true_mt = mt_list[mt_idx]
                    # true_mt = mt
                    if true_mt.type == "neo.event":
                        ev_name = true_mt.metadata['neo_name']
                        ev_id = event_count
                        event_count += 1
                        ev_type = "event"
                        event_channels.append((ev_name, ev_id, ev_type))
                    if true_mt.type == "neo.epoch":
                        ep_name = true_mt.metadata['neo_name']
                        ep_id = epoch_count
                        epoch_count += 1
                        ep_type = "epoch"
                        event_channels.append((ep_name, ep_id, ep_type))
                break
            break
        event_channels = np.array(event_channels, dtype=_event_channel_dtype)

        self.da_list = {'blocks': []}
        for block_index, blk in enumerate(self.file.blocks):
            d = {'segments': []}
            self.da_list['blocks'].append(d)
            for seg_index, _ in enumerate(blk.groups):
                seg = bl.groups[seg_index]
                d = {'signals': []}
                self.da_list['blocks'][block_index]['segments'].append(d)
                size_list = []
                data_list = []
                da_name_list = []
                for da_idx, da in enumerate(seg.data_arrays):
                    true_da = seg.data_arrays[da_idx]
                    if true_da.type == 'neo.analogsignal':
                        size_list.append(true_da.size)
                        data_list.append(true_da)
                        da_name_list.append(true_da.metadata['neo_name'])
                self.da_list['blocks'][block_index]['segments'][seg_index]['data_size'] = size_list
                self.da_list['blocks'][block_index]['segments'][seg_index]['data'] = data_list
                self.da_list['blocks'][block_index]['segments'][seg_index]['ch_name'] = \
                    da_name_list

        self.unit_list = {'blocks': []}
        for block_index, blk in enumerate(self.file.blocks):
            d = {'segments': []}
            self.unit_list['blocks'].append(d)
            for seg_index, _ in enumerate(blk.groups):
                seg = bl.groups[seg_index]
                d = {'spiketrains': [], 'spiketrains_id': [], 'spiketrains_unit': []}
                self.unit_list['blocks'][block_index]['segments'].append(d)
                st_idx = 0
                mt_list = seg.multi_tags
                for mt_idx, mt in enumerate(mt_list):                    
                    true_mt = mt_list[mt_idx]
                    d = {'waveforms': []}
                    self.unit_list[
                        'blocks'][block_index]['segments'][seg_index]['spiketrains_unit'].append(d)
                    if true_mt.type == 'neo.spiketrain':
                        seg = self.unit_list['blocks'][block_index]['segments'][seg_index]
                        seg['spiketrains'].append(true_mt.positions)
                        seg['spiketrains_id'].append(true_mt.id)
                        if true_mt.features and true_mt.features[0].data.type == "neo.waveforms":
                            waveforms = true_mt.features[0].data
                            if waveforms:
                                seg['spiketrains_unit'][st_idx]['waveforms'] = waveforms
                            else:
                                seg['spiketrains_unit'][st_idx]['waveforms'] = None
                            # assume one spiketrain one waveform
                            st_idx += 1

        self.header = {}
        self.header['nb_block'] = len(self.file.blocks)
        self.header['nb_segment'] = [len(bl.groups) for bl in self.file.blocks]
        self.header['signal_channels'] = sig_channels
        self.header['unit_channels'] = unit_channels
        self.header['event_channels'] = event_channels
        self._generate_minimal_annotations()
        for blk_idx, blk in enumerate(self.file.blocks):
            bl_ann = self.raw_annotations['blocks'][blk_idx]
            for props in blk.metadata.inherited_properties():
                self._add_annotate(bl_ann, props, 'blk')
            for seg_index, _ in enumerate(blk.groups):
                seg = bl.groups[seg_index]
                seg_ann = bl_ann['segments'][seg_index]
                for props in seg.metadata.inherited_properties():
                    self._add_annotate(seg_ann, props, 'seg')
                ansig_idx = 0
                for da_idx, da in enumerate(seg.data_arrays):
                    true_da = seg.data_arrays[da_idx]
                    if true_da.type == 'neo.analogsignal' and seg_ann['signals'] != []:
                        ana_an = seg_ann['signals'][ansig_idx]
                        sigch_an = self.raw_annotations['signal_channels'][ansig_idx]
                        for props in true_da.metadata.inherited_properties():
                            self._add_annotate(ana_an, props, 'asig')
                            self._add_annotate(sigch_an, props, 'asig')
                        ansig_idx += 1
                sp_idx = 0
                ev_idx = 0
                mt_list = seg.multi_tags
                for mt_idx, mt in enumerate(mt_list):
                    true_mt = mt_list[mt_idx]
                    if true_mt.type == 'neo.spiketrain' and seg_ann['units'] != []:
                        spiketrain_an = seg_ann['units'][sp_idx]
                        for props in true_mt.metadata.inherited_properties():
                            self._add_annotate(spiketrain_an, props, 'st')
                        sp_idx += 1
                    # if order is preserving, the annotations
                    # should go to the right place, need test
                    if true_mt.type == "neo.event" or true_mt.type == "neo.epoch":
                        if seg_ann['events'] != []:
                            event_an = seg_ann['events'][ev_idx]
                            for props in true_mt.metadata.inherited_properties():
                                self._add_annotate(event_an, props, 'ev')
                            ev_idx += 1

    def _segment_t_start(self, block_index, seg_index):
        t_start = 0
        seg = self.file.blocks[block_index].groups[seg_index]
        mt_list = seg.multi_tags
        for mt_idx, mt in enumerate(mt_list):
            true_mt = mt_list[mt_idx]
            if true_mt.type == "neo.spiketrain":
                t_start = true_mt.metadata['t_start']
        return t_start

    def _segment_t_stop(self, block_index, seg_index):
        t_stop = 0
        seg = self.file.blocks[block_index].groups[seg_index]
        mt_list = seg.multi_tags
        for mt_idx, mt in enumerate(mt_list):
            true_mt = mt_list[mt_idx]
            if true_mt.type == "neo.spiketrain":
                t_stop = true_mt.metadata['t_stop']
        return t_stop

    def _get_signal_size(self, block_index, seg_index, channel_indexes):
        if isinstance(channel_indexes, slice):
            if channel_indexes == slice(None, None, None):
                channel_indexes = list(range(self.header['signal_channels'].size))
            ch_idx = channel_indexes[0]
        else:
            if (channel_indexes is None):
                channel_indexes = list(range(self.header['signal_channels'].size))
            ch_idx = channel_indexes[0]
        size = self.da_list['blocks'][block_index]['segments'][seg_index]['data_size'][ch_idx]
        return size  # size is per signal, not the sum of all channel_indexes

    def _get_signal_t_start(self, block_index, seg_index, channel_indexes):
        if isinstance(channel_indexes, slice):
            if channel_indexes == slice(None, None, None):
                channel_indexes = list(range(self.header['signal_channels'].size))
                ch_idx = channel_indexes[0]
        else:
            if (channel_indexes is None):
                channel_indexes = list(range(self.header['signal_channels'].size))
            ch_idx = channel_indexes[0]
        
        da_list = []
        seg = self.file.blocks[block_index].groups[seg_index]
        for da_idx, da in enumerate(seg.data_arrays):
            da_list.append(seg.data_arrays[da_idx])
        da = da_list[ch_idx]
        sig_t_start = float(da.metadata['t_start'])
        return sig_t_start  # assume same group_id always same t_start

    def _get_analogsignal_chunk(self, block_index, seg_index, i_start, i_stop, channel_indexes):
        
        if isinstance(channel_indexes, slice):
            if channel_indexes == slice(None, None, None):
                channel_indexes = list(range(self.header['signal_channels'].size))
        else:
            if (channel_indexes is None):
                channel_indexes = list(range(self.header['signal_channels'].size))
                
        if i_start is None:
            i_start = 0
        if i_stop is None:
            for c in channel_indexes:
                i_stop = self.da_list['blocks'][block_index]['segments'][seg_index]['data_size'][c]
                break

        raw_signals_list = []
        da_list = self.da_list['blocks'][block_index]['segments'][seg_index]
        for idx in channel_indexes:
            da = da_list['data'][idx]
            raw_signals_list.append(da[i_start:i_stop])

        raw_signals = np.array(raw_signals_list)
        raw_signals = np.transpose(raw_signals)
        return raw_signals

    def _spike_count(self, block_index, seg_index, unit_index):
        count = 0
        head_id = self.header['unit_channels'][unit_index][1]
        seg = self.file.blocks[block_index].groups[seg_index]
        mt_list = seg.multi_tags
        for mt_idx, mt in enumerate(mt_list):
            true_mt = mt_list[mt_idx]
            for src in true_mt.sources:
                if true_mt.type == 'neo.spiketrain' and [src.type == "neo.unit"]:
                    if head_id == src.id:
                        return len(mt.positions)
        return count
    
    def _get_all_spike_timestamps(self, block_index, seg_index, unit_index):
        spike_dict = self.unit_list['blocks'][block_index]['segments'][seg_index]['spiketrains']
        spike_timestamps = spike_dict[unit_index]
        spike_timestamps = np.transpose(spike_timestamps)
        return spike_timestamps

    def _get_spike_timestamps(self, block_index, seg_index, unit_index, t_start, t_stop):
        spike_timestamps = self._get_all_spike_timestamps(
            block_index, seg_index, unit_index)

        if t_start is not None or t_stop is not None:
            lim0 = t_start
            lim1 = t_stop
            mask = (spike_timestamps >= lim0) & (spike_timestamps <= lim1)
            spike_timestamps = spike_timestamps[mask]
        return spike_timestamps

    def _rescale_spike_timestamp(self, spike_timestamps, dtype):
        spike_times = spike_timestamps.astype(dtype)
        return spike_times

    def _get_spike_raw_waveforms(self, block_index, seg_index, unit_index, t_start, t_stop):
        # this must return a 3D numpy array (nb_spike, nb_channel, nb_sample)
        seg = self.unit_list['blocks'][block_index]['segments'][seg_index]
        waveforms = seg['spiketrains_unit'][unit_index]['waveforms']
        if not waveforms:
            return None
        
        raw_waveforms = np.array(waveforms)
        spike_timestamps = self._get_all_spike_timestamps(
            block_index, seg_index, unit_index)
        
        if t_start is not None or t_stop is not None:
            lim0 = t_start
            lim1 = t_stop
            mask = (spike_timestamps >= lim0) & (spike_timestamps <= lim1)
            raw_waveforms = raw_waveforms[mask, :, :]
        return raw_waveforms

    def _event_count(self, block_index, seg_index, event_channel_index):
        event_count = 0
        seg = self.file.blocks[block_index].groups[seg_index]
        mt_list = seg.multi_tags
        for mt_idx, mt in enumerate(mt_list):
            true_mt = mt_list[mt_idx]
            if true_mt.type == 'neo.event' or true_mt.type == 'neo.epoch':
                if event_count == event_channel_index:
                    return len(true_mt.positions)
                else:
                    event_count += 1
        return event_count

    def _get_event_timestamps(self, block_index, seg_index, event_channel_index, t_start, t_stop):
        timestamp = []
        labels = []
        durations = None
        if event_channel_index is None:
            raise IndexError
        seg = self.file.blocks[block_index].groups[seg_index]
        mt_list = seg.multi_tags
        for mt_idx, mt in enumerate(mt_list):
            true_mt = mt_list[mt_idx]
            if true_mt.type == "neo.event" or true_mt.type == "neo.epoch":
                labels.append(true_mt.positions.dimensions[0].labels)
                po = true_mt.positions
                if po.type == "neo.event.times" or po.type == "neo.epoch.times":
                    timestamp.append(po)
                if self.header['event_channels'][event_channel_index]['type'] == b'epoch' \
                        and true_mt.extents:
                    if true_mt.extents.type == 'neo.epoch.durations':
                        durations = np.array(mt.extents)
                        break
        timestamp = timestamp[event_channel_index][:]
        timestamp = np.array(timestamp, dtype="float")
        labels = labels[event_channel_index][:]
        labels = np.array(labels, dtype='U')
        if t_start is not None:
            keep = timestamp >= t_start
            timestamp, labels = timestamp[keep], labels[keep]

        if t_stop is not None:
            keep = timestamp <= t_stop
            timestamp, labels = timestamp[keep], labels[keep]
        return timestamp, durations, labels  # only the first fits in rescale

    def _rescale_event_timestamp(self, event_timestamps, dtype='float64'):
        ev_unit = ''
        seg = self.file.blocks[0].groups[0]
        mt_list = seg.multi_tags
        for mt_idx, mt in enumerate(mt_list):
            true_mt = mt_list[mt_idx]
            if true_mt.type == "neo.event":
                ev_unit = true_mt.positions.unit
                break
        if ev_unit == 'ms':
            event_timestamps /= 1000
        event_times = event_timestamps.astype(dtype)
        # supposing unit is second, other possibilities maybe mS microS...
        return event_times  # return in seconds

    def _rescale_epoch_duration(self, raw_duration, dtype='float64'):
        ep_unit = ''
        seg = self.file.blocks[0].groups[0]
        mt_list = seg.multi_tags
        for mt_idx, mt in enumerate(mt_list):
            true_mt = mt_list[mt_idx]
            if true_mt.type == "neo.epoch":
                ep_unit = true_mt.positions.unit
                break
        if ep_unit == 'ms':
            raw_duration /= 1000
        durations = raw_duration.astype(dtype)
        # supposing unit is second, other possibilities maybe mS microS...
        return durations  # return in seconds

    def _add_annotate(self, tar_ann, props, otype):
        values = props.values
        list_of_param = []
        if otype == 'seg':
            list_of_param = ['index']
        elif otype == 'asig':
            list_of_param = ['units', 'copy', 'sampling_rate', 't_start']
        elif otype == 'st':
            list_of_param = ['units', 'copy', 'sampling_rate',
                             't_start', 't_stop', 'waveforms', 'left_sweep']
        elif otype == 'ev':
            list_of_param = ['times', 'labels', 'units', 'durations', 'copy']
        if len(values) == 1:
            values = values[0]
        if props.name not in list_of_param:
            tar_ann[str(props.name)] = values
        else:
            warntxt = "Name of annotation {} shadows parameter " \
                        "and is therefore dropped".format(props.name)
            #  warnings.warn(warntxt)
