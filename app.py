import sys
import random
import cv2
import numpy as np
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, 
                               QGridLayout, QPushButton, QLabel, QVBoxLayout, 
                               QComboBox, QSpinBox, QSlider, QGroupBox,
                               QHBoxLayout, QTabWidget, QListWidget, QScrollArea,
                               QFrame, QProgressBar)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage

# --- CONSTANTS ---
GRID_SIZE = 10
CELL_SIZE = 70

# Terrain
TERRAIN_PLAINS = 0
TERRAIN_FOREST = 1
TERRAIN_WALL = 2
TERRAIN_WATER = 3

TERRAIN_CHARS = { TERRAIN_PLAINS: "🟩", TERRAIN_FOREST: "🌲", TERRAIN_WALL: "🧱", TERRAIN_WATER: "🌊" }
TERRAIN_COST = { TERRAIN_PLAINS: 1, TERRAIN_FOREST: 2, TERRAIN_WALL: 999, TERRAIN_WATER: 999 }

# Units
class UnitType:
    WARRIOR = "⚔️"
    ARCHER = "🏹"
    TANK = "🛡️"
    CAVALRY = "🐎"    # NEW: Fast, Strong
    MAGE = "🧙"       # NEW: Glass Cannon Ranged
    SIEGE = "💣"      # NEW: Building Destroyer

# HP, ATK, RANGE, SPEED, COST
UNIT_STATS = {
    UnitType.WARRIOR: [25, 7, 1, 3, 10],
    UnitType.ARCHER:  [15, 6, 3, 2, 15],
    UnitType.TANK:    [40, 4, 1, 2, 20],
    UnitType.CAVALRY: [30, 9, 1, 5, 25], # High Speed, High Atk
    UnitType.MAGE:    [10, 12, 3, 2, 30], # Low HP, High Dmg
    UnitType.SIEGE:   [20, 50, 1, 1, 35]  # Huge Dmg vs Buildings
}

# Buildings
class BuildingType:
    CASTLE = "🏰"
    BARRACKS = "🏠"
    TOWER = "🗼"

BUILDING_STATS = {
    BuildingType.CASTLE:   [100, 0, 0], 
    BuildingType.BARRACKS: [50, 0, 0],
    BuildingType.TOWER:    [60, 8, 3]   
}

# Factions
FACTION_DATA = [
    {"name": "Red",    "color": "#e74c3c", "char": "🔴"}, 
    {"name": "Blue",   "color": "#3498db", "char": "🔵"}, 
    {"name": "Green",  "color": "#2ecc71", "char": "🟢"}, 
    {"name": "Yellow", "color": "#f1c40f", "char": "🟡"} 
]

# --- LOGIC CLASSES ---

class Unit:
    def __init__(self, unit_type, team_id, x, y):
        self.type = unit_type
        self.team_id = team_id
        self.x = x
        self.y = y
        stats = UNIT_STATS[unit_type]
        self.max_hp = stats[0]
        self.hp = self.max_hp
        self.attack = stats[1]
        self.range = stats[2]
        self.speed = stats[3]
        self.cost = stats[4]
        self.is_alive = True

    def take_damage(self, amount):
        self.hp -= amount
        if self.hp <= 0:
            self.hp = 0
            self.is_alive = False
        return not self.is_alive

    @property
    def color(self):
        return FACTION_DATA[self.team_id]['color']

class Building:
    def __init__(self, b_type, team_id, x, y):
        self.type = b_type
        self.team_id = team_id
        self.x = x
        self.y = y
        stats = BUILDING_STATS[b_type]
        self.max_hp = stats[0]
        self.hp = self.max_hp
        self.attack = stats[1]
        self.range = stats[2]
        self.is_alive = True

    def take_damage(self, amount):
        self.hp -= amount
        if self.hp <= 0:
            self.hp = 0
            self.is_alive = False
        return not self.is_alive
    
    @property
    def color(self):
        return FACTION_DATA[self.team_id]['color']

class GameState:
    def __init__(self):
        self.grid = [[TERRAIN_PLAINS for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
        self.units = []
        self.buildings = []
        self.gold = [0, 0, 0, 0] 
        self.turn_index = 0
        self.active_factions = 2
        self.game_mode = "Conquest"
        
    def generate_map(self, terrain_cfg, faction_cfgs, game_mode):
        self.units = []
        self.buildings = []
        self.gold = [100, 100, 100, 100] 
        self.game_mode = game_mode
        
        self.grid = [[TERRAIN_PLAINS for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
        for _ in range(terrain_cfg[0]):
            self.grid[random.randint(0, GRID_SIZE-1)][random.randint(0, GRID_SIZE-1)] = TERRAIN_FOREST
        for _ in range(terrain_cfg[1]):
            self.grid[random.randint(0, GRID_SIZE-1)][random.randint(0, GRID_SIZE-1)] = TERRAIN_WALL
        for _ in range(terrain_cfg[2]):
            self.grid[random.randint(0, GRID_SIZE-1)][random.randint(0, GRID_SIZE-1)] = TERRAIN_WATER

        self.active_factions = len(faction_cfgs)
        
        spawn_zones = []
        if self.active_factions == 2:
            spawn_zones = [(1, 2, 1, 3), (GRID_SIZE-3, GRID_SIZE-2, GRID_SIZE-4, GRID_SIZE-2)]
        elif self.active_factions == 3:
            spawn_zones = [(1, 2, 1, 3), (GRID_SIZE-3, GRID_SIZE-2, GRID_SIZE-4, GRID_SIZE-2), (4, 6, 1, 3)]
        elif self.active_factions == 4:
            spawn_zones = [(1, 2, 1, 3), (GRID_SIZE-3, GRID_SIZE-2, GRID_SIZE-4, GRID_SIZE-2), 
                           (1, 3, GRID_SIZE-3, GRID_SIZE-2), (GRID_SIZE-4, GRID_SIZE-2, GRID_SIZE-3, GRID_SIZE-2)]

        for idx, cfg in enumerate(faction_cfgs):
            zone = spawn_zones[idx]
            self.spawn_faction(idx, cfg, zone)

    def spawn_faction(self, team_id, cfg, zone):
        x_min, x_max, y_min, y_max = zone
        
        cx = random.randint(x_min, x_max)
        cy = random.randint(y_min, y_max)
        castle = Building(BuildingType.CASTLE, team_id, cx, cy)
        self.buildings.append(castle)
        
        if self.game_mode == "Conquest":
            for _ in range(1): 
                bx, by = self.find_empty_adjacent(cx, cy)
                if bx:
                    self.buildings.append(Building(BuildingType.BARRACKS, team_id, bx, by))
                    tx, ty = self.find_empty_adjacent(cx, cy)
                    if tx:
                        self.buildings.append(Building(BuildingType.TOWER, team_id, tx, ty))

        # Parse all unit types from config
        all_units = []
        for ut in UNIT_STATS.keys():
            count = cfg.get(ut, 0)
            all_units.extend([ut] * count)
        
        random.shuffle(all_units)
        
        for ut in all_units:
            ux, uy = self.find_empty_adjacent(cx, cy, search_radius=3)
            if ux:
                self.units.append(Unit(ut, team_id, ux, uy))

    def find_empty_adjacent(self, x, y, search_radius=1):
        for r in range(1, search_radius + 1):
            neighbors = [(x-r, y), (x+r, y), (x, y-r), (x, y+r), 
                         (x-r, y-r), (x+r, y+r), (x-r, y+r), (x+r, y-r)]
            random.shuffle(neighbors)
            for nx, ny in neighbors:
                if self.is_passable(nx, ny, ignore_units=False):
                    return nx, ny
        return None, None

    def is_passable(self, x, y, ignore_units=True):
        if not (0 <= x < GRID_SIZE and 0 <= y < GRID_SIZE): return False
        if TERRAIN_COST[self.grid[y][x]] >= 999: return False
        if not ignore_units:
            if self.get_unit_at(x, y): return False
            if self.get_building_at(x, y): return False
        return True

    def get_unit_at(self, x, y):
        for u in self.units:
            if u.x == x and u.y == y and u.is_alive: return u
        return None
    
    def get_building_at(self, x, y):
        for b in self.buildings:
            if b.x == x and b.y == y and b.is_alive: return b
        return None

    def get_team_units(self, team_id):
        return [u for u in self.units if u.team_id == team_id and u.is_alive]
    
    def get_team_buildings(self, team_id):
        return [b for b in self.buildings if b.team_id == team_id and b.is_alive]

    def get_alive_factions(self):
        alive = set()
        for u in self.units:
            if u.is_alive: alive.add(u.team_id)
        if self.game_mode == "Conquest":
            alive_castles = set(b.team_id for b in self.buildings if b.type == BuildingType.CASTLE and b.is_alive)
            return alive.intersection(alive_castles)
        return alive

# --- AI ENGINE ---

class AIEngine:
    @staticmethod
    def get_moves(game, unit):
        moves = []
        for dx in range(-unit.speed, unit.speed + 1):
            for dy in range(-unit.speed, unit.speed + 1):
                if abs(dx) + abs(dy) <= unit.speed:
                    tx, ty = unit.x + dx, unit.y + dy
                    if game.is_passable(tx, ty, ignore_units=False):
                        moves.append((tx, ty))
        return moves

    @staticmethod
    def execute_turn(game, unit, strategy):
        enemies = [u for u in game.units if u.team_id != unit.team_id and u.is_alive]
        enemy_buildings = [b for b in game.buildings if b.team_id != unit.team_id and b.is_alive]
        
        # Priorities based on Unit Type
        if unit.type == UnitType.SIEGE:
            # Siege units prioritize buildings
            targets = enemy_buildings
        else:
            targets = enemies
            
        # Find closest target
        closest_dist = float('inf')
        target_obj = None
        
        for t in targets:
            d = abs(unit.x - t.x) + abs(unit.y - t.y)
            if d < closest_dist:
                closest_dist = d
                target_obj = t
        
        # If no specific targets, look for any enemy (for Siege if no buildings left)
        if not target_obj and enemies:
            target_obj = min(enemies, key=lambda e: abs(unit.x - e.x) + abs(unit.y - e.y))
            closest_dist = abs(unit.x - target_obj.x) + abs(unit.y - target_obj.y)

        # Action Logic
        if target_obj:
            # Attack if in range
            if closest_dist <= unit.range:
                return {"action": "attack", "target": target_obj}
            
            # Move Closer
            moves = AIEngine.get_moves(game, unit)
            if moves:
                best_move = min(moves, key=lambda p: abs(p[0]-target_obj.x) + abs(p[1]-target_obj.y))
                return {"action": "move", "pos": best_move}
                
        return None

    @staticmethod
    def execute_economy(game, team_id):
        current_gold = game.gold[team_id]
        # Simple purchase logic: If rich, buy expensive units. If poor, buy fodder.
        if current_gold >= 50:
            barracks = [b for b in game.get_team_buildings(team_id) if b.type == BuildingType.BARRACKS]
            if barracks:
                bar = random.choice(barracks)
                spawn_x, spawn_y = game.find_empty_adjacent(bar.x, bar.y)
                if spawn_x:
                    # Choose unit based on gold
                    options = [UnitType.WARRIOR, UnitType.ARCHER, UnitType.CAVALRY, UnitType.MAGE]
                    choice = random.choice(options)
                    cost = UNIT_STATS[choice][4]
                    if current_gold >= cost:
                        new_unit = Unit(choice, team_id, spawn_x, spawn_y)
                        game.units.append(new_unit)
                        game.gold[team_id] -= cost
                        return f"💰 {FACTION_DATA[team_id]['name']} recruited {choice}!"
        return None

    @staticmethod
    def building_turn(game, building):
        if building.type == BuildingType.TOWER and building.attack > 0:
            enemies = [u for u in game.units if u.team_id != building.team_id and u.is_alive]
            targets = [e for e in enemies if abs(building.x - e.x) + abs(building.y - e.y) <= building.range]
            if targets:
                target = random.choice(targets)
                return {"action": "attack", "target": target}
        return None

# --- CUSTOM WIDGET FOR CELL ---

class UnitCellWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(CELL_SIZE, CELL_SIZE)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(0)
        
        self.icon_label = QLabel()
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setStyleSheet("font-size: 32px; border: none; background: transparent;")
        
        self.hp_bar = QProgressBar()
        self.hp_bar.setFixedHeight(6)
        self.hp_bar.setTextVisible(False)
        
        layout.addWidget(self.icon_label)
        layout.addWidget(self.hp_bar)
        
        self.set_terrain(TERRAIN_PLAINS)
        self.clear_entity()

    def set_terrain(self, terrain_type):
        colors = {
            TERRAIN_PLAINS: "#4a7c23", TERRAIN_FOREST: "#2d5016", 
            TERRAIN_WALL: "#7f8c8d", TERRAIN_WATER: "#2980b9"
        }
        self.setStyleSheet(f"QWidget {{ background-color: {colors[terrain_type]}; border: 1px solid #222; }}")

    def set_entity(self, entity):
        self.icon_label.setText(entity.type)
        hp_percent = int((entity.hp / entity.max_hp) * 100)
        self.hp_bar.setValue(hp_percent)
        
        color = entity.color
        if hp_percent < 50: color = "#f1c40f" 
        
        self.hp_bar.setStyleSheet(f"""
            QProgressBar {{ background-color: #222; border: none; border-radius: 3px; }} 
            QProgressBar::chunk {{ background-color: {color}; border-radius: 3px; }}
        """)
        self.hp_bar.setVisible(True)

    def clear_entity(self):
        self.icon_label.setText(TERRAIN_CHARS.get(TERRAIN_PLAINS, ""))
        self.hp_bar.setVisible(False)

# --- MAIN WINDOW ---

class BattleSimulator(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("⚔️ Ultimate Battle Simulator: Unit Expansion 👽")
        self.resize(1200, 950) # Taller to fit new UI
        self.game_state = GameState()
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)
        
        # === TAB 1: ARENA ===
        arena_tab = QWidget()
        arena_layout = QVBoxLayout(arena_tab)
        
        top_bar = QHBoxLayout()
        self.turn_label = QLabel("Setup Game")
        self.turn_label.setStyleSheet("font-size: 24px; font-weight: bold;")
        self.gold_labels = [QLabel(f"{FACTION_DATA[i]['char']}: 0g") for i in range(4)]
        
        top_bar.addWidget(self.turn_label)
        top_bar.addStretch()
        for lbl in self.gold_labels: top_bar.addWidget(lbl)
        arena_layout.addLayout(top_bar)
        
        self.board_container = QWidget()
        self.board_grid = QGridLayout(self.board_container)
        self.board_grid.setSpacing(1)
        self.cell_widgets = []
        
        for y in range(GRID_SIZE):
            row = []
            for x in range(GRID_SIZE):
                cell = UnitCellWidget()
                self.board_grid.addWidget(cell, y, x)
                row.append(cell)
            self.cell_widgets.append(row)
            
        h_center = QHBoxLayout()
        h_center.addStretch()
        h_center.addWidget(self.board_container)
        h_center.addStretch()
        arena_layout.addLayout(h_center)
        
        controls_layout = QHBoxLayout()
        self.start_btn = QPushButton("▶️ Start")
        self.start_btn.setStyleSheet("background-color: #27ae60; font-weight: bold;")
        self.start_btn.clicked.connect(self.toggle_simulation)
        
        self.reset_btn = QPushButton("🔄 Apply Settings")
        self.reset_btn.setStyleSheet("background-color: #95a5a6;")
        self.reset_btn.clicked.connect(self.apply_settings)
        
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(50, 1000)
        self.speed_slider.setValue(400)
        self.speed_slider.setInvertedAppearance(True)
        
        controls_layout.addWidget(self.start_btn)
        controls_layout.addWidget(self.reset_btn)
        controls_layout.addWidget(QLabel("Speed:"))
        controls_layout.addWidget(self.speed_slider)
        arena_layout.addLayout(controls_layout)
        
        self.tabs.addTab(arena_tab, "🏟️ Arena")

        # === TAB 2: SETTINGS ===
        settings_tab = QWidget()
        settings_layout = QVBoxLayout(settings_tab)
        
        # Global
        g_global = QGroupBox("🌐 Global Settings")
        glay = QGridLayout()
        glay.addWidget(QLabel("Number of Factions:"), 0, 0)
        self.faction_count_spin = QSpinBox()
        self.faction_count_spin.setRange(2, 4)
        self.faction_count_spin.setValue(2)
        self.faction_count_spin.valueChanged.connect(self.rebuild_faction_ui)
        glay.addWidget(self.faction_count_spin, 0, 1)
        
        glay.addWidget(QLabel("Game Mode:"), 1, 0)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Conquest (Buildings)", "Skirmish (Units Only)"])
        glay.addWidget(self.mode_combo, 1, 1)
        g_global.setLayout(glay)
        settings_layout.addWidget(g_global)

        # Map
        g_map = QGroupBox("🗺️ Map")
        flay = QGridLayout()
        self.spin_forest = QSpinBox(); self.spin_forest.setValue(8);
        self.spin_wall = QSpinBox(); self.spin_wall.setValue(4);
        self.spin_water = QSpinBox(); self.spin_water.setValue(3);
        
        flay.addWidget(QLabel("🌲 Forests:"), 0, 0); flay.addWidget(self.spin_forest, 0, 1)
        flay.addWidget(QLabel("🧱 Walls:"), 1, 0); flay.addWidget(self.spin_wall, 1, 1)
        flay.addWidget(QLabel("🌊 Water:"), 2, 0); flay.addWidget(self.spin_water, 2, 1)
        g_map.setLayout(flay)
        settings_layout.addWidget(g_map)

        # Factions
        self.faction_scroll = QScrollArea()
        self.faction_scroll.setWidgetResizable(True)
        self.faction_scroll_widget = QWidget()
        self.faction_scroll_layout = QVBoxLayout(self.faction_scroll_widget)
        self.faction_scroll.setWidget(self.faction_scroll_widget)
        settings_layout.addWidget(self.faction_scroll)
        
        self.faction_widgets = []
        self.tabs.addTab(settings_tab, "⚙️ Settings")

        # === TAB 3: STATS ===
        stats_tab = QWidget()
        stats_layout = QVBoxLayout(stats_tab)
        self.log_list = QListWidget()
        self.log_list.setStyleSheet("font-family: Consolas; font-size: 12px;")
        stats_layout.addWidget(QLabel("📜 Battle Log"))
        stats_layout.addWidget(self.log_list)
        self.tabs.addTab(stats_tab, "📊 Statistics")
        
        # Logic
        self.ai_timer = QTimer()
        self.ai_timer.timeout.connect(self.game_loop)
        self.is_running = False
        
        self.rebuild_faction_ui()
        self.apply_settings()

    def rebuild_faction_ui(self):
        for i in reversed(range(self.faction_scroll_layout.count())): 
            self.faction_scroll_layout.itemAt(i).widget().setParent(None)
        self.faction_widgets = []
        
        count = self.faction_count_spin.value()
        
        for i in range(count):
            data = FACTION_DATA[i]
            group = QGroupBox(f"{data['char']} {data['name']} Faction")
            glay = QGridLayout()
            
            # Spinboxes for ALL unit types
            spin_war = QSpinBox(); spin_war.setValue(2)
            spin_arc = QSpinBox(); spin_arc.setValue(1)
            spin_tnk = QSpinBox(); spin_tnk.setValue(0)
            spin_cav = QSpinBox(); spin_cav.setValue(1) # New
            spin_mag = QSpinBox(); spin_mag.setValue(0) # New
            spin_sig = QSpinBox(); spin_sig.setValue(0) # New
            
            ai_combo = QComboBox()
            ai_combo.addItems(["Aggressor", "Tactician", "Defender"])
            
            # Row 1
            glay.addWidget(QLabel(f"{UnitType.WARRIOR}:"), 0, 0); glay.addWidget(spin_war, 0, 1)
            glay.addWidget(QLabel(f"{UnitType.ARCHER}:"), 0, 2); glay.addWidget(spin_arc, 0, 3)
            glay.addWidget(QLabel(f"{UnitType.TANK}:"), 0, 4); glay.addWidget(spin_tnk, 0, 5)
            
            # Row 2 (New Units)
            glay.addWidget(QLabel(f"{UnitType.CAVALRY}:"), 1, 0); glay.addWidget(spin_cav, 1, 1)
            glay.addWidget(QLabel(f"{UnitType.MAGE}:"), 1, 2); glay.addWidget(spin_mag, 1, 3)
            glay.addWidget(QLabel(f"{UnitType.SIEGE}:"), 1, 4); glay.addWidget(spin_sig, 1, 5)
            
            glay.addWidget(QLabel("AI:"), 2, 0); glay.addWidget(ai_combo, 2, 1)
            
            group.setLayout(glay)
            group.setStyleSheet(f"QGroupBox {{ color: {data['color']}; font-weight: bold; border: 2px solid {data['color']}; border-radius: 5px; margin-top: 10px; padding-top: 10px; }} QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 3px; }}")
            
            self.faction_scroll_layout.addWidget(group)
            self.faction_widgets.append({ 
                'ai': ai_combo, 
                UnitType.WARRIOR: spin_war, 
                UnitType.ARCHER: spin_arc, 
                UnitType.TANK: spin_tnk,
                UnitType.CAVALRY: spin_cav,
                UnitType.MAGE: spin_mag,
                UnitType.SIEGE: spin_sig
            })
            
        self.faction_scroll_layout.addStretch()

    def apply_settings(self):
        self.is_running = False
        self.start_btn.setText("▶️ Start")
        self.ai_timer.stop()
        
        mode = "Conquest" if "Conquest" in self.mode_combo.currentText() else "Skirmish"
        
        faction_cfgs = []
        for w in self.faction_widgets:
            cfg = { 'ai': w['ai'].currentText() }
            for ut in UNIT_STATS.keys():
                cfg[ut] = w[ut].value()
            faction_cfgs.append(cfg)
            
        terrain_cfg = (self.spin_forest.value(), self.spin_wall.value(), self.spin_water.value())
        self.game_state.generate_map(terrain_cfg, faction_cfgs, mode)
        
        self.log_list.clear()
        self.log(f"Mode: {mode}")
        if mode == "Conquest":
            self.log("🏰 Protect your Castle! Destroy the enemy!")
            self.log("💰 Barracks generate Gold for units.")
        else:
            self.log("⚔️ Skirmish: Destroy all enemies!")
            
        self.update_gold_ui()
        self.redraw_board()
        self.turn_label.setText("Ready")

    def update_gold_ui(self):
        for i in range(4):
            if i < self.game_state.active_factions:
                self.gold_labels[i].setText(f"{FACTION_DATA[i]['char']}: {self.game_state.gold[i]}g")
                self.gold_labels[i].setVisible(True)
            else:
                self.gold_labels[i].setVisible(False)

    def log(self, text):
        self.log_list.addItem(text)
        self.log_list.scrollToBottom()

    def redraw_board(self):
        for y in range(GRID_SIZE):
            for x in range(GRID_SIZE):
                cell = self.cell_widgets[y][x]
                terrain = self.game_state.grid[y][x]
                cell.set_terrain(terrain)
                cell.clear_entity()
                
        for b in self.game_state.buildings:
            if b.is_alive:
                self.cell_widgets[b.y][b.x].set_entity(b)
                
        for u in self.game_state.units:
            if u.is_alive:
                self.cell_widgets[u.y][u.x].set_entity(u)

    def toggle_simulation(self):
        if self.is_running:
            self.is_running = False
            self.ai_timer.stop()
            self.start_btn.setText("▶️ Resume")
        else:
            self.is_running = True
            self.ai_timer.start(self.speed_slider.value())
            self.start_btn.setText("⏸️ Pause")

    def game_loop(self):
        alive = self.game_state.get_alive_factions()
        if len(alive) <= 1:
            winner = alive.pop() if alive else None
            name = FACTION_DATA[winner]['name'] if winner is not None else "Nobody"
            self.end_game(f"🏆 {name} Wins!")
            return

        self.ai_timer.setInterval(self.speed_slider.value())

        current_team_id = self.game_state.turn_index
        
        while current_team_id not in self.game_state.get_alive_factions():
             self.game_state.turn_index = (self.game_state.turn_index + 1) % self.game_state.active_factions
             current_team_id = self.game_state.turn_index

        # Economy
        if self.game_state.game_mode == "Conquest":
            income = 0
            for b in self.game_state.get_team_buildings(current_team_id):
                if b.type == BuildingType.BARRACKS: income += 10
            self.game_state.gold[current_team_id] += income
            
            msg = AIEngine.execute_economy(self.game_state, current_team_id)
            if msg: self.log(msg)
            self.update_gold_ui()

        # Unit Actions
        units = self.game_state.get_team_units(current_team_id)
        if units:
            unit = random.choice(units)
            ai_strat = self.faction_widgets[current_team_id]['ai'].currentText()
            action = AIEngine.execute_turn(self.game_state, unit, ai_strat)
            if action: self.process_action(unit, action)
        
        # Building Actions
        if self.game_state.game_mode == "Conquest":
            buildings = self.game_state.get_team_buildings(current_team_id)
            for b in buildings:
                action = AIEngine.building_turn(self.game_state, b)
                if action: self.process_action(b, action)

        self.game_state.turn_index = (self.game_state.turn_index + 1) % self.game_state.active_factions
        self.turn_label.setText(f"Turn: {FACTION_DATA[self.game_state.turn_index]['name']}")
        self.redraw_board()

    def process_action(self, source, action):
        if action["action"] == "move":
            source.x, source.y = action["pos"]
        elif action["action"] == "attack":
            target = action["target"]
            dmg = source.attack
            killed = target.take_damage(dmg)
            
            src_name = FACTION_DATA[source.team_id]['name']
            tgt_name = FACTION_DATA[target.team_id]['name']
            
            if killed:
                t_type = target.type
                self.log(f"💀 {src_name} {source.type} killed {tgt_name} {t_type}!")

    def end_game(self, msg):
        self.is_running = False
        self.ai_timer.stop()
        self.start_btn.setText("▶️ Start")
        self.turn_label.setText(msg)
        self.log(msg)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = BattleSimulator()
    window.show()
    sys.exit(app.exec())