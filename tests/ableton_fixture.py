"""Synthetic stand-in for a Live-exported one-pad Drum Rack template.

Not a real Ableton file — just the elements rackbuilder touches, in the
same shape Live 12 writes them (GroupDevicePreset/BranchPresets/
DrumBranchPreset, a Simpler with one MultiSamplePart, ZoneSettings), plus
an unrelated element that must survive untouched.
"""

from __future__ import annotations

import gzip
from pathlib import Path

TEMPLATE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Ableton MajorVersion="5" MinorVersion="12.0_12300" SchemaChangeCount="1" Creator="Ableton Live 12.4.6" Revision="">
\t<GroupDevicePreset>
\t\t<OverwriteProtectionNumber Value="3075" />
\t\t<Device>
\t\t\t<DrumGroupDevice Id="0">
\t\t\t\t<UserName Value="" />
\t\t\t\t<Branches />
\t\t\t</DrumGroupDevice>
\t\t</Device>
\t\t<BranchPresets>
\t\t\t<DrumBranchPreset Id="0">
\t\t\t\t<Name Value="Template Pad" />
\t\t\t\t<IsSoloed Value="false" />
\t\t\t\t<DevicePresets>
\t\t\t\t\t<AbletonDevicePreset Id="0">
\t\t\t\t\t\t<Device>
\t\t\t\t\t\t\t<OriginalSimpler Id="0">
\t\t\t\t\t\t\t\t<Player>
\t\t\t\t\t\t\t\t\t<MultiSampleMap>
\t\t\t\t\t\t\t\t\t\t<SampleParts>
\t\t\t\t\t\t\t\t\t\t\t<MultiSamplePart Id="0">
\t\t\t\t\t\t\t\t\t\t\t\t<Name Value="placeholder" />
\t\t\t\t\t\t\t\t\t\t\t\t<SampleStart Value="10" />
\t\t\t\t\t\t\t\t\t\t\t\t<SampleEnd Value="999" />
\t\t\t\t\t\t\t\t\t\t\t\t<SustainLoop>
\t\t\t\t\t\t\t\t\t\t\t\t\t<Start Value="0" />
\t\t\t\t\t\t\t\t\t\t\t\t\t<End Value="999" />
\t\t\t\t\t\t\t\t\t\t\t\t</SustainLoop>
\t\t\t\t\t\t\t\t\t\t\t\t<SampleRef>
\t\t\t\t\t\t\t\t\t\t\t\t\t<FileRef>
\t\t\t\t\t\t\t\t\t\t\t\t\t\t<RelativePathType Value="5" />
\t\t\t\t\t\t\t\t\t\t\t\t\t\t<RelativePath Value="old/placeholder.wav" />
\t\t\t\t\t\t\t\t\t\t\t\t\t\t<Path Value="C:/Users/me/placeholder.wav" />
\t\t\t\t\t\t\t\t\t\t\t\t\t\t<Type Value="2" />
\t\t\t\t\t\t\t\t\t\t\t\t\t\t<LivePackName Value="Core Library" />
\t\t\t\t\t\t\t\t\t\t\t\t\t\t<LivePackId Value="www.ableton.com/0" />
\t\t\t\t\t\t\t\t\t\t\t\t\t\t<OriginalFileSize Value="1234" />
\t\t\t\t\t\t\t\t\t\t\t\t\t\t<OriginalCrc Value="4321" />
\t\t\t\t\t\t\t\t\t\t\t\t\t</FileRef>
\t\t\t\t\t\t\t\t\t\t\t\t\t<DefaultDuration Value="999" />
\t\t\t\t\t\t\t\t\t\t\t\t\t<DefaultSampleRate Value="48000" />
\t\t\t\t\t\t\t\t\t\t\t\t</SampleRef>
\t\t\t\t\t\t\t\t\t\t\t</MultiSamplePart>
\t\t\t\t\t\t\t\t\t\t</SampleParts>
\t\t\t\t\t\t\t\t\t</MultiSampleMap>
\t\t\t\t\t\t\t\t</Player>
\t\t\t\t\t\t\t</OriginalSimpler>
\t\t\t\t\t\t</Device>
\t\t\t\t\t</AbletonDevicePreset>
\t\t\t\t</DevicePresets>
\t\t\t\t<ZoneSettings>
\t\t\t\t\t<ReceivingNote Value="92" />
\t\t\t\t\t<SendingNote Value="60" />
\t\t\t\t\t<ChokeGroup Value="0" />
\t\t\t\t</ZoneSettings>
\t\t\t</DrumBranchPreset>
\t\t</BranchPresets>
\t</GroupDevicePreset>
</Ableton>
"""


def write_template(path: Path, xml: str = TEMPLATE_XML) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(gzip.compress(xml.encode("utf-8")))
    return path
