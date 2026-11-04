# Copyright (C) 2026 librarianistxyz <https://github.com/librarianistxyz/OmniCam>
#
# This file is part of OmniCam: AI Virtual Multi-Camera Director.
#
# OmniCam is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# OmniCam is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""
CapCut & Studio Blend Mode Looping Overlay Engine for OmniCam.
Provides 50+ cinematic video textures, retro film loops, Oppenheimer atomic effects,
Sherlock Holmes Victorian atmospheric palettes, and sci-fi holographic telemetry.
"""

import os
import subprocess
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class OverlayPreset:
    id: str
    title: str
    category: str
    filename: str
    description: str
    recommended_blend: str = "screen"
    default_opacity: float = 0.85
    lavfi_filter: Optional[str] = None
    duration: float = 3.0


# ------------------------------------------------------------------------------
# 54 CURATED STUDIO OVERLAY PRESETS ACROSS 6 DISTINCT CATEGORIES
# ------------------------------------------------------------------------------
OVERLAY_PRESETS: List[OverlayPreset] = [
    # ==========================================================================
    # CATEGORY 1: OPPENHEIMER & ATOMIC SUITE (8 Presets)
    # ==========================================================================
    OverlayPreset(
        id="oppenheimer_trinity_fire",
        title="Oppenheimer Trinity Fire",
        category="Oppenheimer & Atomic",
        filename="oppenheimer_trinity_fire.mp4",
        description="Scorched fiery nuclear fission embers & atmospheric plasma flames (Los Alamos Trinity test).",
        recommended_blend="screen",
        default_opacity=0.85,
        duration=3.0,
        lavfi_filter=(
            "color=c=black:s=160x90:d=3:r=24,"
            "geq=r='240*pow(max(0,sin(X/25+T*3.1)*cos(Y/18+T*2.4)),1.4)+40':"
            "g='110*pow(max(0,sin(X/28+T*2.8)*cos(Y/20+T*2.1)),2.0)+15':"
            "b='10':a='255',scale=1280:720:flags=bicubic,boxblur=22:2"
        ),
    ),
    OverlayPreset(
        id="oppenheimer_imax_mono",
        title="Oppenheimer 70mm Monochrome",
        category="Oppenheimer & Atomic",
        filename="oppenheimer_imax_mono.mp4",
        description="IMAX 70mm high-contrast black & white silver halide grain & negative gate breathing.",
        recommended_blend="screen",
        default_opacity=0.75,
        duration=3.0,
        lavfi_filter=(
            "color=c=black:s=1280x720:d=3:r=24,noise=alls=26:allf=t+u,"
            "curves=all='0/0 0.88/0 0.98/0.88 1/1',scale=1280:720:flags=bicubic,boxblur=1:1"
        ),
    ),
    OverlayPreset(
        id="oppenheimer_radiation_glow",
        title="Cherenkov Radiation Glow",
        category="Oppenheimer & Atomic",
        filename="oppenheimer_radiation_glow.mp4",
        description="Luminous Cherenkov radiation ultraviolet-cyan reactor pulse & eerie halo bloom.",
        recommended_blend="screen",
        default_opacity=0.80,
        duration=3.0,
        lavfi_filter=(
            "color=c=black:s=160x90:d=3:r=24,"
            "geq=r='15*pow(cos(X/30+T*2.2),2)':"
            "g='130*pow(cos(X/25+T*2.0)*sin(Y/20+T*1.8),2)+20':"
            "b='245*pow(sin(Y/25+T*2.4),2)+45':a='255',"
            "scale=1280:720:flags=bicubic,boxblur=26:2"
        ),
    ),
    OverlayPreset(
        id="oppenheimer_quantum_waves",
        title="Oppenheimer Quantum Waves",
        category="Oppenheimer & Atomic",
        filename="oppenheimer_quantum_waves.mp4",
        description="Theoretical subatomic wave-particle interference fringes & probability ripples.",
        recommended_blend="screen",
        default_opacity=0.85,
        duration=3.0,
        lavfi_filter=(
            "color=c=black:s=320x180:d=3:r=24,"
            "geq=r='180*pow(0.5+0.5*sin(hypot(X-160,Y-90)/6-T*7),4)':"
            "g='90*pow(0.5+0.5*sin(hypot(X-160,Y-90)/6-T*7),4)':"
            "b='20':a='255',scale=1280:720:flags=bicubic,boxblur=8:2"
        ),
    ),
    OverlayPreset(
        id="oppenheimer_atomic_sparks",
        title="Fission Reactor Sparks",
        category="Oppenheimer & Atomic",
        filename="oppenheimer_atomic_sparks.mp4",
        description="Swirling uranium core fission sparks, radiant embers & glowing isotopes.",
        recommended_blend="screen",
        default_opacity=0.85,
        duration=3.0,
        lavfi_filter=(
            "color=c=black:s=640x360:d=3:r=24,noise=alls=14:allf=t+u,"
            "curves=all='0/0 0.93/0 0.98/0.85 1/1',"
            "colorbalance=rs=0.5:gs=0.25:bs=-0.4,scale=1280:720:flags=bicubic,boxblur=2:1"
        ),
    ),
    OverlayPreset(
        id="oppenheimer_los_alamos_dust",
        title="Los Alamos Desert Grit",
        category="Oppenheimer & Atomic",
        filename="oppenheimer_los_alamos_dust.mp4",
        description="Arid New Mexico desert windblown micro-grit, sun glare & atmospheric thermal shimmer.",
        recommended_blend="screen",
        default_opacity=0.75,
        duration=3.0,
        lavfi_filter=(
            "color=c=black:s=160x90:d=3:r=24,"
            "geq=r='170*pow(sin(X/35+T*1.5)*cos(Y/25+T*1.1),2)+35':"
            "g='110*pow(sin(X/35+T*1.5)*cos(Y/25+T*1.1),2)+20':"
            "b='30*pow(sin(X/35+T*1.5)*cos(Y/25+T*1.1),2)':a='255',"
            "scale=1280:720:flags=bicubic,boxblur=28:2"
        ),
    ),
    OverlayPreset(
        id="oppenheimer_fission_burst",
        title="Oppenheimer Nuclear Strobe",
        category="Oppenheimer & Atomic",
        filename="oppenheimer_fission_burst.mp4",
        description="Blinding atomic chain-reaction strobe flashes and expanding fireball luminance.",
        recommended_blend="screen",
        default_opacity=0.90,
        duration=2.5,
        lavfi_filter=(
            "color=c=black:s=160x90:d=2.5:r=24,"
            "geq=r='255*pow(max(0,sin(T*12)),6)':"
            "g='180*pow(max(0,sin(T*12)),6)':"
            "b='70*pow(max(0,sin(T*12)),6)':a='255',"
            "scale=1280:720:flags=bicubic,boxblur=25:2"
        ),
    ),
    OverlayPreset(
        id="oppenheimer_trinity_shockwave",
        title="Trinity Blast Shockwave",
        category="Oppenheimer & Atomic",
        filename="oppenheimer_trinity_shockwave.mp4",
        description="Supersonic pressure shockwave refraction ring expanding across the frame.",
        recommended_blend="screen",
        default_opacity=0.85,
        duration=3.0,
        lavfi_filter=(
            "color=c=black:s=320x180:d=3:r=24,"
            "geq=r='200*max(0,1-abs(hypot(X-160,Y-90)-mod(T*90\\,200))/12)':"
            "g='140*max(0,1-abs(hypot(X-160,Y-90)-mod(T*90\\,200))/12)':"
            "b='40*max(0,1-abs(hypot(X-160,Y-90)-mod(T*90\\,200))/12)':a='255',"
            "scale=1280:720:flags=bicubic,boxblur=10:2"
        ),
    ),

    # ==========================================================================
    # CATEGORY 2: SHERLOCK & VICTORIAN NOIR (8 Presets)
    # ==========================================================================
    OverlayPreset(
        id="sherlock_baker_st_fog",
        title="Baker St. Victorian Fog",
        category="Sherlock & Victorian",
        filename="sherlock_baker_st_fog.mp4",
        description="Dense London Thames river fog and 1890s coal-smoke mist rolling across the street.",
        recommended_blend="screen",
        default_opacity=0.85,
        duration=3.0,
        lavfi_filter=(
            "color=c=black:s=160x90:d=3:r=24,"
            "geq=r='90*sin(X/40+T*0.7)*sin(Y/30+T*0.5)+45':"
            "g='105*sin(X/38+T*0.6)*sin(Y/28+T*0.5)+50':"
            "b='110*sin(X/35+T*0.7)*sin(Y/26+T*0.6)+55':a='255',"
            "scale=1280:720:flags=bicubic,boxblur=32:2"
        ),
    ),
    OverlayPreset(
        id="sherlock_gaslamp_glow",
        title="Sherlock Gaslamp Lantern",
        category="Sherlock & Victorian",
        filename="sherlock_gaslamp_glow.mp4",
        description="Flickering Victorian street gaslamp amber flare, soot halo & warm cobblestone glow.",
        recommended_blend="screen",
        default_opacity=0.85,
        duration=3.0,
        lavfi_filter=(
            "color=c=black:s=160x90:d=3:r=24,"
            "geq=r='(210+25*sin(T*15))*pow(max(0,1-hypot(X-25,Y-25)/80),2)':"
            "g='(135+18*sin(T*15))*pow(max(0,1-hypot(X-25,Y-25)/80),2)':"
            "b='20*pow(max(0,1-hypot(X-25,Y-25)/80),2)':a='255',"
            "scale=1280:720:flags=bicubic,boxblur=24:2"
        ),
    ),
    OverlayPreset(
        id="sherlock_cobblestone_rain",
        title="London Cobblestone Rain",
        category="Sherlock & Victorian",
        filename="sherlock_cobblestone_rain.mp4",
        description="Moody vertical English drizzle, rain streaks and wet dark pavement reflections.",
        recommended_blend="screen",
        default_opacity=0.80,
        duration=3.0,
        lavfi_filter=(
            "color=c=black:s=640x360:d=3:r=24,noise=alls=22:allf=t+u,"
            "curves=all='0/0 0.92/0 0.98/0.7 1/1',scale=1280:720:flags=bicubic,boxblur=1:1"
        ),
    ),
    OverlayPreset(
        id="sherlock_pipe_smoke",
        title="Meerschaum Pipe Smoke",
        category="Sherlock & Victorian",
        filename="sherlock_pipe_smoke.mp4",
        description="Graceful swirling tobacco smoke tendrils rising lazily through the study.",
        recommended_blend="screen",
        default_opacity=0.75,
        duration=3.0,
        lavfi_filter=(
            "color=c=black:s=160x90:d=3:r=24,"
            "geq=r='95*pow(max(0,sin(X/20+sin(Y/15)+T*1.8)*cos(Y/25-T*1.2)),2)':"
            "g='100*pow(max(0,sin(X/20+sin(Y/15)+T*1.8)*cos(Y/25-T*1.2)),2)':"
            "b='105*pow(max(0,sin(X/20+sin(Y/15)+T*1.8)*cos(Y/25-T*1.2)),2)':a='255',"
            "scale=1280:720:flags=bicubic,boxblur=20:2"
        ),
    ),
    OverlayPreset(
        id="sherlock_victorian_dust",
        title="Victorian Study Dust Motes",
        category="Sherlock & Victorian",
        filename="sherlock_victorian_dust.mp4",
        description="Suspended vintage room dust motes illuminated by leaded window sunbeams.",
        recommended_blend="screen",
        default_opacity=0.75,
        duration=3.0,
        lavfi_filter=(
            "color=c=black:s=640x360:d=3:r=24,noise=alls=10:allf=t+u,"
            "curves=all='0/0 0.95/0 0.99/0.8 1/1',"
            "colorbalance=rs=0.15:gs=0.12:bs=-0.1,scale=1280:720:flags=bicubic,boxblur=2:1"
        ),
    ),
    OverlayPreset(
        id="sherlock_candlelight_flicker",
        title="Candlelight Nocturne",
        category="Sherlock & Victorian",
        filename="sherlock_candlelight_flicker.mp4",
        description="Intimate 221B Baker Street oscillating candlelight glow and breathing shadows.",
        recommended_blend="screen",
        default_opacity=0.85,
        duration=3.0,
        lavfi_filter=(
            "color=c=black:s=160x90:d=3:r=24,"
            "geq=r='(160+30*sin(T*22)+15*cos(T*11))*pow(max(0,1-hypot(X-135,Y-70)/90),1.8)':"
            "g='(95+20*sin(T*22)+10*cos(T*11))*pow(max(0,1-hypot(X-135,Y-70)/90),1.8)':"
            "b='15':a='255',scale=1280:720:flags=bicubic,boxblur=25:2"
        ),
    ),
    OverlayPreset(
        id="sherlock_wet_carriage_glass",
        title="Hansom Cab Window Rain",
        category="Sherlock & Victorian",
        filename="sherlock_wet_carriage_glass.mp4",
        description="Soft blurred droplets trickling down the glass of a Victorian carriage window.",
        recommended_blend="screen",
        default_opacity=0.80,
        duration=3.0,
        lavfi_filter=(
            "color=c=black:s=320x180:d=3:r=24,noise=alls=12:allf=t+u,"
            "curves=all='0/0 0.93/0 0.98/0.8 1/1',scale=1280:720:flags=bicubic,boxblur=4:2"
        ),
    ),
    OverlayPreset(
        id="sherlock_antique_parchment",
        title="1895 Archive Parchment",
        category="Sherlock & Victorian",
        filename="sherlock_antique_parchment.mp4",
        description="Aged yellowed manuscript texture, tea-stain border vignette & fiber grain.",
        recommended_blend="screen",
        default_opacity=0.75,
        duration=3.0,
        lavfi_filter=(
            "color=c=black:s=640x360:d=3:r=24,noise=alls=8:allf=t+u,"
            "curves=all='0/0 0.9/0 0.98/0.7 1/1',colorbalance=rs=0.25:gs=0.15:bs=-0.25,"
            "vignette=PI/4,scale=1280:720:flags=bicubic"
        ),
    ),

    # ==========================================================================
    # CATEGORY 3: VINTAGES & OLD FILMS (12 Presets)
    # ==========================================================================
    OverlayPreset(
        id="vintage_super8",
        title="Super 8mm Projector",
        category="Vintages & Old Films",
        filename="vintage_super8.mp4",
        description="Super 8mm vintage projector gate flicker, corner vignetting & organic jitter.",
        recommended_blend="screen",
        default_opacity=0.75,
        duration=2.5,
        lavfi_filter=(
            "color=c=black:s=1280x720:d=2.5:r=24,noise=alls=18:allf=t+u,"
            "curves=all='0/0 0.85/0 0.97/0.7 1/1',"
            "vignette='PI/4 + 0.05*sin(t*18)',scale=1280:720:flags=lanczos"
        ),
    ),
    OverlayPreset(
        id="vintage_16mm_grain",
        title="16mm French New Wave Grain",
        category="Vintages & Old Films",
        filename="vintage_16mm_grain.mp4",
        description="French New Wave 16mm Kodak Tri-X silver halide organic grain & gate breathing.",
        recommended_blend="screen",
        default_opacity=0.75,
        duration=3.0,
        lavfi_filter=(
            "color=c=black:s=1280x720:d=3:r=24,noise=alls=24:allf=t+u,"
            "curves=all='0/0 0.88/0 0.98/0.8 1/1',scale=1280:720:flags=bicubic,boxblur=1:1"
        ),
    ),
    OverlayPreset(
        id="vintage_35mm_dust",
        title="35mm Cinema Reel Scratches",
        category="Vintages & Old Films",
        filename="vintage_35mm_dust.mp4",
        description="35mm cinema reel scratches, black hair artifacts, and organic dust specks.",
        recommended_blend="screen",
        default_opacity=0.75,
        duration=2.5,
        lavfi_filter=(
            "color=c=black:s=1280x720:d=2.5:r=24,noise=alls=15:allf=t+u,"
            "curves=all='0/0 0.9/0 0.98/0.85 1/1',"
            "drawbox=x='mod(t*850\\,1200)':y=0:w=1:h=720:color=white@0.6:t=fill:enable='eq(mod(n\\,12)\\,0)',"
            "drawbox=x='mod(t*620\\,1240)':y=0:w=2:h=720:color=white@0.4:t=fill:enable='eq(mod(n\\,20)\\,0)'"
        ),
    ),
    OverlayPreset(
        id="vintage_nitrate_burn",
        title="1920s Nitrate Celluloid Burn",
        category="Vintages & Old Films",
        filename="vintage_nitrate_burn.mp4",
        description="Flammable nitrate film edge melting and burning amber flare.",
        recommended_blend="screen",
        default_opacity=0.85,
        duration=2.5,
        lavfi_filter=(
            "color=c=black:s=160x90:d=2.5:r=24,"
            "geq=r='245*pow(sin(X/30+T*3.5),2)':g='110*pow(sin(X/30+T*3.5),3)':b='15':a='255',"
            "scale=1280:720:flags=bicubic,boxblur=25:2"
        ),
    ),
    OverlayPreset(
        id="vintage_silent_1920",
        title="Silent Cinema Jitter (1920)",
        category="Vintages & Old Films",
        filename="vintage_silent_1920.mp4",
        description="1920s silent film gate weave, frame stutter, and optical vignetting.",
        recommended_blend="screen",
        default_opacity=0.80,
        duration=2.5,
        lavfi_filter=(
            "color=c=black:s=1280x720:d=2.5:r=24,noise=alls=35:allf=t+u,"
            "curves=all='0/0 0.82/0 0.96/0.85 1/1',vignette='PI/3.5+0.08*sin(t*24)'"
        ),
    ),
    OverlayPreset(
        id="vintage_technicolor_leak",
        title="Technicolor 3-Strip Bleed",
        category="Vintages & Old Films",
        filename="vintage_technicolor_leak.mp4",
        description="3-strip dye transfer magenta and cyan optical light bleed at edge gates.",
        recommended_blend="screen",
        default_opacity=0.80,
        duration=3.0,
        lavfi_filter=(
            "color=c=black:s=160x90:d=3:r=24,"
            "geq=r='180*max(0,sin(X/30-T*1.8))':g='40*max(0,cos(Y/25+T*1.2))':"
            "b='170*max(0,sin(Y/28+T*2.0))':a='255',scale=1280:720:flags=bicubic,boxblur=26:2"
        ),
    ),
    OverlayPreset(
        id="vintage_kodachrome_64",
        title="Kodachrome 64 Golden Haze",
        category="Vintages & Old Films",
        filename="vintage_kodachrome_64.mp4",
        description="Warm 1970s Kodachrome slide color bleeding and golden sunlight wash.",
        recommended_blend="screen",
        default_opacity=0.80,
        duration=3.0,
        lavfi_filter=(
            "color=c=black:s=160x90:d=3:r=24,"
            "geq=r='185*pow(cos(X/40+T*1.3),2)+45':g='125*pow(cos(X/40+T*1.3),2)+25':"
            "b='35*pow(cos(X/40+T*1.3),4)':a='255',scale=1280:720:flags=bicubic,boxblur=28:2"
        ),
    ),
    OverlayPreset(
        id="vintage_film_leader",
        title="Projector Leader Countdown",
        category="Vintages & Old Films",
        filename="vintage_film_leader.mp4",
        description="Mechanical countdown leader frame flash, sprockets, and framing crosshairs.",
        recommended_blend="screen",
        default_opacity=0.75,
        duration=2.5,
        lavfi_filter=(
            "color=c=black:s=640x360:d=2.5:r=24,"
            "drawgrid=w=320:h=180:color=white@0.22:t=1,"
            "drawbox=x=319:y=0:w=2:h=360:color=white@0.5:t=fill,"
            "drawbox=x=0:y=179:w=640:h=2:color=white@0.5:t=fill,"
            "vignette=PI/4,scale=1280:720:flags=neighbor"
        ),
    ),
    OverlayPreset(
        id="vintage_damaged_tape",
        title="VHS Magnetic Oxide Loss",
        category="Vintages & Old Films",
        filename="vintage_damaged_tape.mp4",
        description="Damaged videotape magnetic oxide loss, horizontal noise snow, and line dropouts.",
        recommended_blend="screen",
        default_opacity=0.70,
        duration=2.5,
        lavfi_filter=(
            "color=c=black:s=640x360:d=2.5:r=24,noise=alls=20:allf=t+u,"
            "drawbox=x=0:y='mod(t*320\\,360)':w=640:h=22:color=white@0.35:t=fill,"
            "drawgrid=w=640:h=4:color=white@0.12:t=1,scale=1280:720:flags=neighbor"
        ),
    ),
    OverlayPreset(
        id="vintage_polaroid_fade",
        title="Polaroid SX-70 Chemistry",
        category="Vintages & Old Films",
        filename="vintage_polaroid_fade.mp4",
        description="1980s instant film chemical dispersion, pastel milky blacks & soft border fog.",
        recommended_blend="screen",
        default_opacity=0.75,
        duration=3.0,
        lavfi_filter=(
            "color=c=black:s=160x90:d=3:r=24,"
            "geq=r='110*pow(cos(Y/28+T*1.1),2)+35':g='120*pow(cos(Y/28+T*1.1),2)+40':"
            "b='130*pow(cos(Y/28+T*1.1),2)+45':a='255',scale=1280:720:flags=bicubic,boxblur=26:2"
        ),
    ),
    OverlayPreset(
        id="vintage_sepia_saloon",
        title="1880 Daguerreotype Sepia",
        category="Vintages & Old Films",
        filename="vintage_sepia_saloon.mp4",
        description="19th-century daguerreotype antique sepia toning, edge corrosion & silver tarnish.",
        recommended_blend="screen",
        default_opacity=0.75,
        duration=3.0,
        lavfi_filter=(
            "color=c=black:s=160x90:d=3:r=24,"
            "geq=r='150*pow(sin(X/35+T*0.9),2)+45':g='105*pow(sin(X/35+T*0.9),2)+25':"
            "b='35':a='255',vignette=PI/3.2,scale=1280:720:flags=bicubic,boxblur=24:2"
        ),
    ),
    OverlayPreset(
        id="vintage_drive_in_grain",
        title="Drive-in Projector Beam",
        category="Vintages & Old Films",
        filename="vintage_drive_in_grain.mp4",
        description="Outdoor drive-in projector light dust beam and fluttering reel flutter.",
        recommended_blend="screen",
        default_opacity=0.75,
        duration=3.0,
        lavfi_filter=(
            "color=c=black:s=640x360:d=3:r=24,noise=alls=14:allf=t+u,"
            "curves=all='0/0 0.92/0 0.98/0.8 1/1',"
            "drawbox=x=0:y='mod(t*220\\,360)':w=640:h=40:color=white@0.08:t=fill,"
            "scale=1280:720:flags=bicubic,boxblur=3:1"
        ),
    ),

    # ==========================================================================
    # CATEGORY 4: LIGHT LEAKS, FILM BURNS & PRISMS (10 Presets)
    # ==========================================================================
    OverlayPreset(
        id="light_leak_01",
        title="Golden Flare Leak",
        category="Light Leaks & Burns",
        filename="light_leak_01.mp4",
        description="Warm golden flares & amber ambient edge leaks (CapCut golden hour look).",
        recommended_blend="screen",
        default_opacity=0.85,
        duration=3.0,
        lavfi_filter=(
            "color=c=black:s=160x90:d=3:r=24,"
            "geq=r='190*sin(X/35+T*2.2)*sin(Y/22+T*1.6)+65':"
            "g='110*sin(X/38+T*2.0)*sin(Y/25+T*1.3)+35':"
            "b='15*sin(X/50+T)*sin(Y/30+T)':a='255',"
            "scale=1280:720:flags=bicubic,boxblur=28:2"
        ),
    ),
    OverlayPreset(
        id="light_leak_02",
        title="Sunset Crimson Burst",
        category="Light Leaks & Burns",
        filename="light_leak_02.mp4",
        description="Vivid sunset magenta and neon crimson pulses for dramatic emotional cuts.",
        recommended_blend="screen",
        default_opacity=0.80,
        duration=3.0,
        lavfi_filter=(
            "color=c=black:s=160x90:d=3:r=24,"
            "geq=r='200*sin(X/30+T*2.5)*sin(Y/25+T*1.8)+55':"
            "g='45*sin(X/45+T*1.5)*sin(Y/30+T*1.1)+15':"
            "b='120*sin(X/35+T*2.1)*sin(Y/28+T*1.4)+30':a='255',"
            "scale=1280:720:flags=bicubic,boxblur=28:2"
        ),
    ),
    OverlayPreset(
        id="light_leak_warm_radial",
        title="Halogen Corner Flare",
        category="Light Leaks & Burns",
        filename="light_leak_warm_radial.mp4",
        description="Rotating corner lens flare orb and soft warm halogen light wash.",
        recommended_blend="screen",
        default_opacity=0.85,
        duration=3.0,
        lavfi_filter=(
            "color=c=black:s=160x90:d=3:r=24,"
            "geq=r='220*pow(max(0,1-hypot(X-30,Y-20)/90),2)':"
            "g='140*pow(max(0,1-hypot(X-30,Y-20)/90),2)':"
            "b='25*pow(max(0,1-hypot(X-30,Y-20)/90),2)':a='255',"
            "scale=1280:720:flags=bicubic,boxblur=26:2"
        ),
    ),
    OverlayPreset(
        id="light_leak_cyan_streak",
        title="Anamorphic Cyan Laser Streak",
        category="Light Leaks & Burns",
        filename="light_leak_cyan_streak.mp4",
        description="Sci-fi laser anamorphic horizontal cyan beam with specular flare star.",
        recommended_blend="screen",
        default_opacity=0.85,
        duration=3.0,
        lavfi_filter=(
            "color=c=black:s=320x180:d=3:r=24,"
            "drawbox=x=0:y='88+sin(t*3)*15':w=320:h=4:color=0x00E5FF@0.85:t=fill,"
            "drawbox=x='150+cos(t*2)*80':y='85+sin(t*3)*15':w=20:h=10:color=white@0.9:t=fill,"
            "scale=1280:720:flags=bicubic,boxblur=22:2"
        ),
    ),
    OverlayPreset(
        id="film_burn_01",
        title="Fiery Celluloid Burn",
        category="Light Leaks & Burns",
        filename="film_burn_01.mp4",
        description="High-intensity amber & orange film burn edge burst with halation.",
        recommended_blend="screen",
        default_opacity=0.85,
        duration=2.5,
        lavfi_filter=(
            "color=c=black:s=160x90:d=2.5:r=24,"
            "geq=r='230*pow(sin(X/40+T*3),2)':g='90*pow(sin(X/40+T*3),3)':"
            "b='10*pow(sin(X/40+T*3),4)':a='255',scale=1280:720:flags=bicubic,boxblur=30:2"
        ),
    ),
    OverlayPreset(
        id="film_burn_02",
        title="Edge Halation Burn",
        category="Light Leaks & Burns",
        filename="film_burn_02.mp4",
        description="Deep crimson gate halation burn with organic edge flicker.",
        recommended_blend="screen",
        default_opacity=0.80,
        duration=2.5,
        lavfi_filter=(
            "color=c=black:s=160x90:d=2.5:r=24,"
            "geq=r='240*pow(cos(Y/30+T*2.8),2)':g='160*pow(cos(Y/30+T*2.8),2)':"
            "b='30*pow(cos(Y/30+T*2.8),4)':a='255',scale=1280:720:flags=bicubic,boxblur=26:2"
        ),
    ),
    OverlayPreset(
        id="film_burn_slow_amber",
        title="Slow Amber Smolder",
        category="Light Leaks & Burns",
        filename="film_burn_slow_amber.mp4",
        description="Organic smoldering frame boundary fire bleed and slow thermal decay.",
        recommended_blend="screen",
        default_opacity=0.80,
        duration=3.0,
        lavfi_filter=(
            "color=c=black:s=160x90:d=3:r=24,"
            "geq=r='220*pow(sin(X/35+T*1.8)*sin(Y/25+T*1.4),2)+40':"
            "g='120*pow(sin(X/35+T*1.8)*sin(Y/25+T*1.4),3)+15':b='10':a='255',"
            "scale=1280:720:flags=bicubic,boxblur=25:2"
        ),
    ),
    OverlayPreset(
        id="film_burn_solar_white",
        title="Solarized White-out Burn",
        category="Light Leaks & Burns",
        filename="film_burn_solar_white.mp4",
        description="High-energy solarized white-out film burn transition with golden fringes.",
        recommended_blend="screen",
        default_opacity=0.85,
        duration=2.5,
        lavfi_filter=(
            "color=c=black:s=160x90:d=2.5:r=24,"
            "geq=r='255*pow(max(0,sin(T*8)),4)':g='240*pow(max(0,sin(T*8)),4)':"
            "b='200*pow(max(0,sin(T*8)),4)':a='255',scale=1280:720:flags=bicubic,boxblur=28:2"
        ),
    ),
    OverlayPreset(
        id="prism_bokeh",
        title="Dreamy Prism Bokeh",
        category="Light Leaks & Burns",
        filename="prism_bokeh.mp4",
        description="Floating hexagonal light discs, optical refraction & dreamy bokeh flare.",
        recommended_blend="screen",
        default_opacity=0.85,
        duration=3.0,
        lavfi_filter=(
            "color=c=black:s=320x180:d=3:r=24,"
            "geq=r='140*pow(cos(X/25+T*1.4)*sin(Y/20-T),4)':"
            "g='120*pow(cos(X/28+T*1.6+1)*sin(Y/22-T*1.2),4)':"
            "b='160*pow(cos(X/22+T*1.2+2)*sin(Y/18-T*0.8),4)':a='255',"
            "scale=1280:720:flags=bicubic,boxblur=15:2"
        ),
    ),
    OverlayPreset(
        id="prism_refraction_halo",
        title="Crystal Spectral Halo",
        category="Light Leaks & Burns",
        filename="prism_refraction_halo.mp4",
        description="Triangular crystal prism spectral rainbow beam and optical ring halo.",
        recommended_blend="screen",
        default_opacity=0.85,
        duration=3.0,
        lavfi_filter=(
            "color=c=black:s=320x180:d=3:r=24,"
            "geq=r='180*pow(max(0,sin(atan2(Y-90,X-160)*3+T*2.5)),3)':"
            "g='140*pow(max(0,sin(atan2(Y-90,X-160)*3+T*2.5+1)),3)':"
            "b='200*pow(max(0,sin(atan2(Y-90,X-160)*3+T*2.5+2)),3)':a='255',"
            "scale=1280:720:flags=bicubic,boxblur=18:2"
        ),
    ),

    # ==========================================================================
    # CATEGORY 5: SCI-FI & CYBERPUNK (10 Presets)
    # ==========================================================================
    OverlayPreset(
        id="cyber_hud_matrix",
        title="Cyber Telemetry HUD",
        category="Sci-Fi & Cyberpunk",
        filename="cyber_hud_matrix.mp4",
        description="Futuristic holographic targeting rings, telemetry grid, coordinate crosshairs & radar scan.",
        recommended_blend="screen",
        default_opacity=0.85,
        duration=3.0,
        lavfi_filter=(
            "color=c=black:s=640x360:d=3:r=24,"
            "drawgrid=w=64:h=64:color=0x00E5FF@0.14:t=1,"
            "drawbox=x=30:y=30:w=80:h=3:color=0x00F0FF@0.8:t=fill,"
            "drawbox=x=30:y=30:w=3:h=60:color=0x00F0FF@0.8:t=fill,"
            "drawbox=x=530:y=30:w=80:h=3:color=0x00F0FF@0.8:t=fill,"
            "drawbox=x=607:y=30:w=3:h=60:color=0x00F0FF@0.8:t=fill,"
            "drawbox=x=30:y=327:w=80:h=3:color=0x00F0FF@0.8:t=fill,"
            "drawbox=x=30:y=270:w=3:h=60:color=0x00F0FF@0.8:t=fill,"
            "drawbox=x=530:y=327:w=80:h=3:color=0x00F0FF@0.8:t=fill,"
            "drawbox=x=607:y=270:w=3:h=60:color=0x00F0FF@0.8:t=fill,"
            "drawbox=x=0:y='mod(t*180\\,360)':w=640:h=2:color=0x00F0FF@0.4:t=fill,"
            "scale=1280:720:flags=neighbor"
        ),
    ),
    OverlayPreset(
        id="holo_matrix_grid",
        title="Hologram Matrix Grid",
        category="Sci-Fi & Cyberpunk",
        filename="holo_matrix_grid.mp4",
        description="3D cyber wireframe floor & wall matrix grid with glowing data sweep pulses (Tron / Cyberpunk).",
        recommended_blend="screen",
        default_opacity=0.80,
        duration=3.0,
        lavfi_filter=(
            "color=c=black:s=640x360:d=3:r=24,"
            "drawgrid=w=32:h=24:color=0x00FF88@0.18:t=1,"
            "drawbox=x='mod(t*240\\,640)':y=0:w=3:h=360:color=0x00FFCC@0.5:t=fill,"
            "drawbox=x=0:y='mod(t*160\\,360)':w=640:h=3:color=0x00FF88@0.3:t=fill,"
            "scale=1280:720:flags=bicubic"
        ),
    ),
    OverlayPreset(
        id="neural_circuit_core",
        title="Neural Circuit Core",
        category="Sci-Fi & Cyberpunk",
        filename="neural_circuit_core.mp4",
        description="Glowing electronic circuit board traces, neon microchip interconnects & data packets.",
        recommended_blend="screen",
        default_opacity=0.85,
        duration=3.0,
        lavfi_filter=(
            "color=c=black:s=640x360:d=3:r=24,"
            "drawgrid=w=128:h=72:color=0x8A2BE2@0.22:t=1,"
            "drawbox=x=64:y='mod(t*200\\,360)':w=12:h=12:color=0x00F0FF@0.75:t=fill,"
            "drawbox=x=450:y='360-mod(t*220\\,360)':w=10:h=10:color=0xFF00AA@0.75:t=fill,"
            "scale=1280:720:flags=neighbor"
        ),
    ),
    OverlayPreset(
        id="tactical_sonar_radar",
        title="Tactical Sonar Radar",
        category="Sci-Fi & Cyberpunk",
        filename="tactical_sonar_radar.mp4",
        description="Sci-fi circular radar sweep beam with telemetry sonar concentric rings.",
        recommended_blend="screen",
        default_opacity=0.80,
        duration=3.0,
        lavfi_filter=(
            "color=c=black:s=360x360:d=3:r=24,"
            "geq=r='180*max(0,cos(atan2(Y-180,X-180)-T*3.5))':"
            "g='240*max(0,cos(atan2(Y-180,X-180)-T*3.5))':"
            "b='255*max(0,cos(atan2(Y-180,X-180)-T*3.5))':a='255',"
            "scale=1280:720:flags=bicubic,boxblur=10:2"
        ),
    ),
    OverlayPreset(
        id="quantum_particles_stream",
        title="Quantum Particles Stream",
        category="Sci-Fi & Cyberpunk",
        filename="quantum_particles_stream.mp4",
        description="Floating upward luminescent cyber dust nodes and data packet bokeh stream.",
        recommended_blend="screen",
        default_opacity=0.85,
        duration=3.0,
        lavfi_filter=(
            "color=c=black:s=640x360:d=3:r=24,noise=alls=16:allf=t+u,"
            "curves=all='0/0 0.92/0 0.98/0.88 1/1',"
            "colorbalance=rs=-0.2:gs=0.3:bs=0.5,boxblur=2:1,scale=1280:720:flags=bicubic"
        ),
    ),
    OverlayPreset(
        id="glitch_digital",
        title="Cyber Digital Glitch",
        category="Sci-Fi & Cyberpunk",
        filename="glitch_digital.mp4",
        description="Chromatic RGB displacement blocks and futuristic electronic glitch slices.",
        recommended_blend="screen",
        default_opacity=0.70,
        duration=2.0,
        lavfi_filter=(
            "color=c=black:s=640x360:d=2:r=24,"
            "drawbox=x='mod(t*750\\,480)':y='mod(t*530\\,300)':w='160':h='20':color=cyan@0.65:t=fill:enable='eq(mod(n\\,9)\\,0)',"
            "drawbox=x='mod(t*620\\,440)':y='mod(t*410\\,320)':w='200':h='14':color=red@0.65:t=fill:enable='eq(mod(n\\,9)\\,0)',"
            "scale=1280:720:flags=neighbor"
        ),
    ),
    OverlayPreset(
        id="retro_crt_scanlines",
        title="Cyber CRT Scanlines",
        category="Sci-Fi & Cyberpunk",
        filename="retro_crt_scanlines.mp4",
        description="Analog broadcast television CRT lines and horizontal beam sweeps.",
        recommended_blend="screen",
        default_opacity=0.65,
        duration=2.0,
        lavfi_filter=(
            "color=c=black:s=1280x720:d=2:r=24,"
            "drawgrid=w=1280:h=3:color=white@0.18:t=1,"
            "drawbox=x=0:y='mod(t*220\\,720)':w=1280:h=32:color=white@0.12:t=fill"
        ),
    ),
    OverlayPreset(
        id="vhs_static_overlay",
        title="90s Retro VHS Static",
        category="Sci-Fi & Cyberpunk",
        filename="vhs_static_overlay.mp4",
        description="Magnetic tape noise, horizontal tracking jitter & nostalgic CRT static.",
        recommended_blend="screen",
        default_opacity=0.70,
        duration=2.5,
        lavfi_filter=(
            "color=c=black:s=640x360:d=2.5:r=24,noise=alls=15:allf=t+u,"
            "drawgrid=w=640:h=4:color=white@0.08:t=1,"
            "drawbox=x=0:y='mod(t*180\\,360)':w=640:h=18:color=white@0.22:t=fill,"
            "curves=all='0/0 0.7/0 0.95/0.8 1/1',scale=1280:720:flags=neighbor"
        ),
    ),
    OverlayPreset(
        id="cyber_matrix_rain",
        title="Terminal Glyph Rain",
        category="Sci-Fi & Cyberpunk",
        filename="cyber_matrix_rain.mp4",
        description="Falling matrix phosphorescent code cascade and cyber terminal text pulse.",
        recommended_blend="screen",
        default_opacity=0.80,
        duration=3.0,
        lavfi_filter=(
            "color=c=black:s=640x360:d=3:r=24,"
            "drawgrid=w=16:h=32:color=0x00FF66@0.12:t=1,"
            "drawbox=x='mod(t*370\\,640)':y='mod(t*280\\,360)':w=8:h=24:color=0x00FF88@0.7:t=fill,"
            "scale=1280:720:flags=neighbor"
        ),
    ),
    OverlayPreset(
        id="cyber_hex_shield",
        title="Honeycomb Forcefield Mesh",
        category="Sci-Fi & Cyberpunk",
        filename="cyber_hex_shield.mp4",
        description="Glowing defensive energy shield hex mesh with luminous pulse nodes.",
        recommended_blend="screen",
        default_opacity=0.80,
        duration=3.0,
        lavfi_filter=(
            "color=c=black:s=640x360:d=3:r=24,"
            "drawgrid=w=48:h=48:color=0x00E5FF@0.18:t=1,"
            "drawbox=x='mod(t*200\\,640)':y='mod(t*150\\,360)':w=48:h=48:color=0x00F0FF@0.25:t=fill,"
            "scale=1280:720:flags=bicubic"
        ),
    ),

    # ==========================================================================
    # CATEGORY 6: ATMOSPHERE & PARTICLES (6 Presets)
    # ==========================================================================
    OverlayPreset(
        id="golden_particles",
        title="Floating Golden Motes",
        category="Atmosphere & Particles",
        filename="golden_particles.mp4",
        description="Warm floating dust motes and soft bokeh embers for luxury aesthetic.",
        recommended_blend="screen",
        default_opacity=0.75,
        duration=3.0,
        lavfi_filter=(
            "color=c=black:s=640x360:d=3:r=24,noise=alls=10:allf=t+u,"
            "curves=all='0/0 0.94/0 0.99/0.9 1/1',"
            "colorbalance=rs=0.4:gs=0.2:bs=-0.3,boxblur=2:1,scale=1280:720:flags=bicubic"
        ),
    ),
    OverlayPreset(
        id="cinema_smoke_fog",
        title="Volumetric Stage Haze",
        category="Atmosphere & Particles",
        filename="cinema_smoke_fog.mp4",
        description="Stage smoke haze with gentle atmospheric rolling fog and depth diffusion.",
        recommended_blend="screen",
        default_opacity=0.75,
        duration=3.0,
        lavfi_filter=(
            "color=c=black:s=160x90:d=3:r=24,"
            "geq=r='80*sin(X/35+T*0.8)*sin(Y/25+T*0.6)+30':"
            "g='85*sin(X/35+T*0.8)*sin(Y/25+T*0.6)+35':"
            "b='95*sin(X/35+T*0.8)*sin(Y/25+T*0.6)+40':a='255',"
            "scale=1280:720:flags=bicubic,boxblur=30:2"
        ),
    ),
    OverlayPreset(
        id="snow_frost_drift",
        title="Winter Snow Flurries",
        category="Atmosphere & Particles",
        filename="snow_frost_drift.mp4",
        description="Gentle falling winter snow flakes and crystalline frost bokeh.",
        recommended_blend="screen",
        default_opacity=0.80,
        duration=3.0,
        lavfi_filter=(
            "color=c=black:s=640x360:d=3:r=24,noise=alls=16:allf=t+u,"
            "curves=all='0/0 0.94/0 0.99/0.9 1/1',"
            "colorbalance=rs=-0.1:gs=0.1:bs=0.3,scale=1280:720:flags=bicubic,boxblur=2:1"
        ),
    ),
    OverlayPreset(
        id="ember_fire_sparks",
        title="Soaring Campfire Embers",
        category="Atmosphere & Particles",
        filename="ember_fire_sparks.mp4",
        description="Natural crackling fire embers soaring upwards with warm orange illumination.",
        recommended_blend="screen",
        default_opacity=0.85,
        duration=3.0,
        lavfi_filter=(
            "color=c=black:s=640x360:d=3:r=24,noise=alls=14:allf=t+u,"
            "curves=all='0/0 0.94/0 0.99/0.92 1/1',"
            "colorbalance=rs=0.5:gs=0.2:bs=-0.4,scale=1280:720:flags=bicubic,boxblur=2:1"
        ),
    ),
    OverlayPreset(
        id="lens_dirt_grime",
        title="Front Element Lens Grime",
        category="Atmosphere & Particles",
        filename="lens_dirt_grime.mp4",
        description="Front lens element specular dust spots, micro-smudges & cinematic texture.",
        recommended_blend="screen",
        default_opacity=0.70,
        duration=3.0,
        lavfi_filter=(
            "color=c=black:s=640x360:d=3:r=24,noise=alls=10:allf=t+u,"
            "curves=all='0/0 0.92/0 0.98/0.7 1/1',boxblur=3:2,scale=1280:720:flags=bicubic"
        ),
    ),
    OverlayPreset(
        id="stage_concert_lasers",
        title="Sweeping Concert Lasers",
        category="Atmosphere & Particles",
        filename="stage_concert_lasers.mp4",
        description="Sweeping concert stage volumetric cyan and magenta laser fans.",
        recommended_blend="screen",
        default_opacity=0.85,
        duration=3.0,
        lavfi_filter=(
            "color=c=black:s=320x180:d=3:r=24,"
            "drawbox=x=0:y='85+sin(t*4)*30':w=320:h=3:color=0x00FFCC@0.85:t=fill,"
            "drawbox=x=0:y='95+cos(t*4)*30':w=320:h=3:color=0xFF00AA@0.85:t=fill,"
            "scale=1280:720:flags=bicubic,boxblur=15:2"
        ),
    ),
]


class OverlayEngine:
    """
    Manages discovering, generating, and blending video loop overlay textures.
    Supports standard blend modes: 'screen', 'addition', 'overlay', 'lighten', 'softlight'.
    """

    SUPPORTED_BLEND_MODES = [
        "screen",
        "addition",
        "overlay",
        "lighten",
        "softlight",
        "dodge",
        "multiply",
    ]

    def __init__(self, assets_dir: str = "assets/overlays"):
        self.assets_dir = os.path.abspath(assets_dir)
        os.makedirs(self.assets_dir, exist_ok=True)

    @classmethod
    def get_presets(cls) -> List[OverlayPreset]:
        return OVERLAY_PRESETS

    @classmethod
    def get_categories(cls) -> List[str]:
        seen = []
        for p in OVERLAY_PRESETS:
            if p.category not in seen:
                seen.append(p.category)
        return seen

    @classmethod
    def get_preset_by_id(cls, preset_id: str) -> Optional[OverlayPreset]:
        for p in OVERLAY_PRESETS:
            if p.id == preset_id or p.filename == preset_id:
                return p
        return None

    def get_overlay_path(self, identifier: str) -> Optional[str]:
        """Resolves preset id, filename, or direct file path to an existing overlay video."""
        if not identifier:
            return None

        # Check if it's already an existing file path
        if os.path.isfile(identifier):
            return os.path.abspath(identifier)

        # Check in assets/overlays
        candidate = os.path.join(self.assets_dir, identifier)
        if os.path.isfile(candidate):
            return candidate

        # Check with .mp4 suffix
        if not identifier.endswith(".mp4"):
            candidate_mp4 = os.path.join(self.assets_dir, f"{identifier}.mp4")
            if os.path.isfile(candidate_mp4):
                return candidate_mp4

        # Check preset filename
        preset = self.get_preset_by_id(identifier)
        if preset:
            p_path = os.path.join(self.assets_dir, preset.filename)
            if os.path.isfile(p_path):
                return p_path

            # Auto-synthesize on demand if it's a known preset
            self.generate_preset(preset, p_path)
            if os.path.isfile(p_path):
                return p_path

        return None

    def list_available_overlays(self) -> List[Dict]:
        """Lists all built-in and user-provided overlay video loops."""
        overlays = []

        # Built-in presets
        for preset in OVERLAY_PRESETS:
            file_path = os.path.join(self.assets_dir, preset.filename)
            exists = os.path.isfile(file_path)
            overlays.append({
                "id": preset.id,
                "title": preset.title,
                "category": preset.category,
                "filename": preset.filename,
                "description": preset.description,
                "recommended_blend": preset.recommended_blend,
                "default_opacity": preset.default_opacity,
                "duration": preset.duration,
                "available": exists,
                "path": file_path if exists else None,
                "is_custom": False,
            })

        # Discover any custom MP4 / MOV videos dropped into assets/overlays
        if os.path.isdir(self.assets_dir):
            known_filenames = {p.filename for p in OVERLAY_PRESETS}
            for entry in sorted(os.listdir(self.assets_dir)):
                if entry in known_filenames:
                    continue
                ext = os.path.splitext(entry)[1].lower()
                if ext in (".mp4", ".mov", ".mkv", ".webm"):
                    full_p = os.path.join(self.assets_dir, entry)
                    title_name = os.path.splitext(entry)[0].replace("_", " ").title()
                    overlays.append({
                        "id": entry,
                        "title": f"Custom: {title_name}",
                        "category": "User Uploads",
                        "filename": entry,
                        "description": f"Custom overlay texture ({entry})",
                        "recommended_blend": "screen",
                        "default_opacity": 0.85,
                        "duration": 0.0,
                        "available": True,
                        "path": full_p,
                        "is_custom": True,
                    })

        return overlays

    def generate_preset(self, preset: OverlayPreset, output_path: str) -> bool:
        """Synthesizes a lightweight looping overlay video texture using FFmpeg lavfi."""
        if not preset.lavfi_filter:
            return False

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        cmd = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel", "error",
            "-f", "lavfi",
            "-i", preset.lavfi_filter,
            "-t", f"{preset.duration:.2f}",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "22",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            output_path,
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return res.returncode == 0
        except Exception as ex:
            print(f"  [!] Failed to synthesize overlay {preset.filename}: {ex}")
            return False

    def ensure_all_presets(self, progress_callback=None) -> int:
        """Ensures all standard overlay textures exist in assets/overlays."""
        count = 0
        total = len(OVERLAY_PRESETS)
        for i, p in enumerate(OVERLAY_PRESETS):
            out_file = os.path.join(self.assets_dir, p.filename)
            if not os.path.isfile(out_file):
                if progress_callback:
                    progress_callback(i / total, f"Generating overlay texture '{p.title}'...")
                ok = self.generate_preset(p, out_file)
                if ok:
                    count += 1
            else:
                count += 1
        return count

    @classmethod
    def build_blend_filtergraph(
        cls,
        base_video_label: str,
        overlay_input_idx: int,
        blend_mode: str = "screen",
        opacity: float = 0.85,
        target_width: int = 1920,
        target_height: int = 1080,
        output_label: str = "v_blended",
        background_only: bool = False,
        person_center_x: float = 0.50,
        person_center_y: float = 0.48,
    ) -> Tuple[List[str], str]:
        """
        Builds FFmpeg filter complex fragment to scale/crop the looping overlay video
        and blend it over the main video with the specified blend mode and opacity.
        If background_only=True, applies a feathered subject isolation mask centered on the
        tracked person, leaving the face and speaker completely clean and natural.
        """
        mode = blend_mode.lower()
        if mode not in cls.SUPPORTED_BLEND_MODES:
            mode = "screen"

        opacity = max(0.0, min(1.0, float(opacity)))

        if not background_only:
            filter_lines = [
                # Scale and crop looping overlay to perfectly cover target aspect ratio
                f"[{overlay_input_idx}:v]scale={target_width}:{target_height}:force_original_aspect_ratio=increase,"
                f"crop={target_width}:{target_height},setsar=1[v_ov_scaled]",
                # Blend onto base video
                f"{base_video_label}[v_ov_scaled]blend=all_mode='{mode}':all_opacity={opacity:.2f}[{output_label}]",
            ]
        else:
            px = max(0.15, min(0.85, float(person_center_x)))
            py = max(0.20, min(0.80, float(person_center_y)))
            filter_lines = [
                # Scale and crop looping overlay to perfectly cover target aspect ratio
                f"[{overlay_input_idx}:v]scale={target_width}:{target_height}:force_original_aspect_ratio=increase,"
                f"crop={target_width}:{target_height},setsar=1[v_ov_scaled]",
                # Create blended overlay video
                f"{base_video_label}[v_ov_scaled]blend=all_mode='{mode}':all_opacity={opacity:.2f}[v_ov_all]",
                # Generate feathered subject-isolation mask centered on tracked person (subject at 0, background at 255)
                f"{base_video_label}format=gray,geq=lum='255*clip(pow(hypot((X-W*{px:.2f})/(W*0.32),(Y-H*{py:.2f})/(H*0.44)),2.5),0,1)',boxblur=18:2[v_bg_mask]",
                # Merge: speaker untouched from base, background enhanced with high-tech overlay
                f"{base_video_label}[v_ov_all][v_bg_mask]maskedmerge[{output_label}]",
            ]
        return filter_lines, f"[{output_label}]"
