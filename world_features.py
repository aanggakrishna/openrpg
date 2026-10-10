"""Small data tables for persistent biome stories and world events."""

STORIES = {
    "meadow": ("Jejak Pertama", "First Footprints", "Tanam atau panen 2 kali", "Plant or harvest twice", "garden", 2, "Lencana Padang", "Meadow Badge"),
    "forest": ("Penjaga Rimba", "Forest Keeper", "Kumpulkan 2 kayu", "Collect 2 wood", "wood", 2, "Lencana Rimba", "Forest Badge"),
    "desert": ("Mata Air Tersembunyi", "Hidden Spring", "Kunjungi 2 tempat", "Visit 2 locations", "explore", 2, "Lencana Oasis", "Oasis Badge"),
    "coast": ("Hasil Laut", "Gifts of the Sea", "Tangkap 2 ikan", "Catch 2 fish", "fish", 2, "Lencana Pesisir", "Coast Badge"),
    "swamp": ("Riset Rawa", "Swamp Research", "Tangkap 1 Pokémon", "Catch a Pokémon", "catch", 1, "Lencana Rawa", "Swamp Badge"),
    "cave": ("Cahaya Dalam Gua", "Light Below", "Kalahkan 2 Pokémon", "Win 2 battles", "battle", 2, "Lencana Gua", "Cavern Badge"),
    "badlands": ("Jalur Penjelajah", "Trailblazer", "Kunjungi 2 tempat", "Visit 2 locations", "explore", 2, "Lencana Tanah Merah", "Badlands Badge"),
    "mountain": ("Puncak Bersalju", "High Summit", "Kalahkan 2 Pokémon", "Win 2 battles", "battle", 2, "Lencana Puncak", "Summit Badge"),
    "volcano": ("Bara yang Padam", "Cooling Embers", "Kalahkan 2 Pokémon", "Win 2 battles", "battle", 2, "Lencana Bara", "Ember Badge"),
    "snow": ("Jejak di Salju", "Tracks in Snow", "Kunjungi 2 tempat", "Visit 2 locations", "explore", 2, "Lencana Salju", "Snow Badge"),
    "sky": ("Pengamat Langit", "Sky Watch", "Tangkap 1 Pokémon", "Catch a Pokémon", "catch", 1, "Lencana Langit", "Sky Badge"),
    "crystal": ("Resonansi Kristal", "Crystal Resonance", "Kalahkan 2 Pokémon", "Win 2 battles", "battle", 2, "Lencana Kristal", "Crystal Badge"),
    "ancient_forest": ("Rerimbun Purba", "Ancient Canopy", "Kumpulkan 2 kayu", "Collect 2 wood", "wood", 2, "Lencana Purba", "Ancient Badge"),
    "deepsea": ("Ekspedisi Laut Dalam", "Deep Sea Expedition", "Tangkap 2 ikan", "Catch 2 fish", "fish", 2, "Lencana Samudra", "Abyss Badge"),
    "dragon_valley": ("Tantangan Naga", "Dragon's Trial", "Menangkan 2 duel", "Win 2 battles", "battle", 2, "Lencana Naga", "Dragon Badge"),
    "legendary_ruins": ("Rahasia Reruntuhan", "Ruins Mystery", "Temukan rahasia tempat ini", "Discover this area's secret", "secret", 1, "Lencana Legenda", "Legend Badge"),
}

# Local tile coordinates inside each 1280x1600 reserve zone. Locations were
# chosen in walkable clearings, away from the zone border and central paths.
SECRETS = {
    "meadow": (550, 350, "🌼"), "forest": (550, 350, "🍄"),
    "desert": (470, 540, "🏺"), "coast": (380, 970, "🐚"),
    "swamp": (450, 1000, "🪷"), "cave": (400, 990, "💎"),
    "badlands": (480, 980, "🦴"), "mountain": (400, 1100, "🧭"),
    "volcano": (450, 1080, "🔥"), "snow": (500, 1040, "❄️"),
    "sky": (420, 1050, "☁️"), "crystal": (470, 1060, "🔮"),
    "ancient_forest": (440, 1100, "🌳"), "deepsea": (500, 1050, "🫧"),
    "dragon_valley": (440, 1100, "🐉"), "legendary_ruins": (500, 1050, "🗝️"),
}

EVENTS = {
    "meadow": [("Wildflower Bloom", "🌸"), ("Berry Rain", "🫐")],
    "forest": [("Forest Berry Rush", "🍓"), ("Bug Migration", "🦋")],
    "desert": [("Dune Cache", "🏜️"), ("Meteor Shard", "☄️")],
    "coast": [("Tidepool Treasure", "🐚"), ("School of Fish", "🐟")],
    "swamp": [("Moonlit Lotus", "🪷"), ("Murk Bloom", "🌿")],
    "cave": [("Crystal Pulse", "💎"), ("Echoing Find", "✨")],
    "badlands": [("Fossil Rush", "🦴"), ("Dust Devil Cache", "🌪️")],
    "mountain": [("Alpine Aurora", "🌌"), ("Falling Star", "⭐")],
    "volcano": [("Lava Glow", "🌋"), ("Emberfall", "🔥")],
    "snow": [("Aurora Snowfall", "❄️"), ("Ice Berry Drift", "🫐")],
    "sky": [("Sky Lanterns", "🏮"), ("Cloudwing Flock", "🪽")],
    "crystal": [("Prism Shower", "🔮"), ("Starlight Shards", "✨")],
    "ancient_forest": [("Ancient Bloom", "🌺"), ("Spirit Fireflies", "🪲")],
    "deepsea": [("Bioluminescent Tide", "🪼"), ("Pearl Current", "🦪")],
    "dragon_valley": [("Dragon's Roost", "🐉"), ("Scalefall", "✨")],
    "legendary_ruins": [("Relic Resonance", "🏛️"), ("Starfall Relic", "☄️")],
}

EVENT_NAMES_ID = {
    "Wildflower Bloom": "Mekarnya Bunga Liar", "Berry Rain": "Hujan Buah Beri",
    "Forest Berry Rush": "Pesta Buah Rimba", "Bug Migration": "Migrasi Serangga",
    "Dune Cache": "Harta Bukit Pasir", "Meteor Shard": "Pecahan Meteor",
    "Tidepool Treasure": "Harta Kolam Pasang", "School of Fish": "Kawanan Ikan",
    "Moonlit Lotus": "Teratai Cahaya Bulan", "Murk Bloom": "Bunga Rawa",
    "Crystal Pulse": "Denyut Kristal", "Echoing Find": "Temuan Gema",
    "Fossil Rush": "Berburu Fosil", "Dust Devil Cache": "Harta Pusaran Debu",
    "Alpine Aurora": "Aurora Pegunungan", "Falling Star": "Bintang Jatuh",
    "Lava Glow": "Cahaya Lava", "Emberfall": "Hujan Bara",
    "Aurora Snowfall": "Salju Aurora", "Ice Berry Drift": "Hanyutan Beri Es",
    "Sky Lanterns": "Lentera Langit", "Cloudwing Flock": "Kawanan Sayap Awan",
    "Prism Shower": "Hujan Prisma", "Starlight Shards": "Pecahan Cahaya Bintang",
    "Ancient Bloom": "Mekar Purba", "Spirit Fireflies": "Kunang-Kunang Roh",
    "Bioluminescent Tide": "Pasang Bioluminesen", "Pearl Current": "Arus Mutiara",
    "Dragon's Roost": "Sarang Naga", "Scalefall": "Hujan Sisik",
    "Relic Resonance": "Resonansi Relik", "Starfall Relic": "Relik Bintang Jatuh",
}

COLLECTIONS = ((5, "Novice Collector", "Kolektor Pemula", 50),
               (15, "Field Researcher", "Peneliti Lapangan", 120),
               (40, "Pokémon Naturalist", "Naturalis Pokémon", 300),
               (100, "Living Pokédex", "Pokédex Hidup", 800))

COLLECTION_COSMETICS = (
    (5, "leaf-crown", "Leaf Crown", "Mahkota Daun"),
    (15, "trail-cloak", "Trail Cloak", "Jubah Penjelajah"),
    (40, "star-aura", "Star Aura", "Aura Bintang"),
    (100, "legend-aura", "Legend Aura", "Aura Legenda"),
)

# A small, retryable field riddle protects each hidden cache.
PUZZLES = {
    "meadow": (("Which type thrives among wildflowers?", "Tipe apa yang tumbuh subur di antara bunga liar?"), ("Grass", "Water", "Steel"), 0),
    "forest": (("Which type is most at home under the canopy?", "Tipe apa yang paling cocok di bawah rimbun hutan?"), ("Bug", "Fire", "Ice"), 0),
    "desert": (("What type rules the shifting dunes?", "Tipe apa yang menguasai bukit pasir?"), ("Water", "Ground", "Fairy"), 1),
    "coast": (("Which type follows the tide?", "Tipe apa yang mengikuti pasang laut?"), ("Water", "Rock", "Fire"), 0),
    "swamp": (("What type hides in the marsh mist?", "Tipe apa yang bersembunyi dalam kabut rawa?"), ("Poison", "Steel", "Ice"), 0),
    "cave": (("Which type echoes through the cavern?", "Tipe apa yang menggema di dalam gua?"), ("Ghost", "Grass", "Fairy"), 0),
    "badlands": (("What type shapes the red earth?", "Tipe apa yang membentuk tanah merah?"), ("Ground", "Water", "Psychic"), 0),
    "mountain": (("Which type endures the frozen summit?", "Tipe apa yang bertahan di puncak beku?"), ("Ice", "Bug", "Poison"), 0),
    "volcano": (("Which type is born in molten rock?", "Tipe apa yang lahir dari batu cair?"), ("Fire", "Water", "Grass"), 0),
    "snow": (("What type leaves tracks in fresh snow?", "Tipe apa yang meninggalkan jejak di salju?"), ("Ice", "Ground", "Electric"), 0),
    "sky": (("Which type rides the high wind?", "Tipe apa yang menunggangi angin tinggi?"), ("Flying", "Rock", "Poison"), 0),
    "crystal": (("What type resonates with crystal light?", "Tipe apa yang beresonansi dengan cahaya kristal?"), ("Psychic", "Fire", "Ground"), 0),
    "ancient_forest": (("Which type guards the old trees?", "Tipe apa yang menjaga pepohonan purba?"), ("Grass", "Steel", "Dark"), 0),
    "deepsea": (("Which type moves through the abyss?", "Tipe apa yang bergerak di palung laut?"), ("Water", "Fire", "Flying"), 0),
    "dragon_valley": (("Which type claims this valley?", "Tipe apa yang menguasai lembah ini?"), ("Dragon", "Bug", "Normal"), 0),
    "legendary_ruins": (("Which type senses an ancient relic?", "Tipe apa yang merasakan relik kuno?"), ("Psychic", "Water", "Grass"), 0),
}

NPC_SCHEDULES = {
    "Sari": (6, 15, "Makanan & obat"),
    "Budi": (9, 20, "Senjata & panah"),
    "Joy": (11, 18, "Pembeli hasil panen"),
}

WEATHER_TYPES = {
    "Hujan": {"water": 1.45, "grass": 1.25, "bug": 1.15, "fire": .82},
    "Salju": {"ice": 1.7, "fire": .82},
    "Badai": {"electric": 1.55, "water": 1.25, "flying": .78},
    "Cerah": {"fire": 1.22, "grass": 1.1},
    "Berawan": {"normal": 1.12, "rock": 1.12, "flying": 1.08},
}
