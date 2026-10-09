"""Studio-only album-inspired presets; these are not official album colors."""
from types import MappingProxyType

MGK_PALETTES = MappingProxyType({name: MappingProxyType(colors) for name, colors in {
    'Tickets to My Downfall': dict(bass='#FF4FA3', mids='#FF92C8', treble='#FFFFFF', beat='#FF1744'),
    'Mainstream Sellout': dict(bass='#FF69B4', mids='#F5F5F5', treble='#F44336', beat='#FF1493'),
    'Hotel Diablo': dict(bass='#50146C', mids='#A020F0', treble='#E63232', beat='#16101E'),
    'Lost Americana': dict(bass='#1677C8', mids='#F5E6CE', treble='#C84D43', beat='#86C8EA'),
    'Lace Up': dict(bass='#D71920', mids='#282828', treble='#E5E5E5', beat='#FF5638'),
    'General Admission': dict(bass='#191919', mids='#626262', treble='#E0D6C8', beat='#B21E35'),
    'Bloom': dict(bass='#E84983', mids='#AF5AC7', treble='#FFCA71', beat='#FF4070'),
    'Binge': dict(bass='#C3F000', mids='#151515', treble='#F2F2F2', beat='#FF482E'),
    'Rap Devil': dict(bass='#B30021', mids='#FF3030', treble='#F2F2F2', beat='#FF6500'),
}.items()})
