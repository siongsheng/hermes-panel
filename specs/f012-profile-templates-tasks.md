# Task Breakdown: F012: Profile Templates

### Task 1: Rename existing dokima init to dokima discover
**Files:** dokima
**Dependencies:** [none]
**Description:** Rename existing dokima init to dokima discover

### Task 2: Implement init_profiles() core function in dokima
**Files:** dokima
**Dependencies:** 1
**Description:** Implement init_profiles() core function in dokima

### Task 3: Wire dokima init (profile mode) into CLI dispatch
**Files:** dokima
**Dependencies:** 2
**Description:** Wire dokima init (profile mode) into CLI dispatch

### Task 4: Update install.sh to call dokima init
**Files:** install.sh
**Dependencies:** 3
**Description:** Update install.sh to call dokima init

### Task 5: Slim down setup-linux.sh profile section
**Files:** scripts/setup-linux.sh
**Dependencies:** 3
**Description:** Slim down setup-linux.sh profile section

### Task 6: Write unit tests for init_profiles()
**Files:** tests/test_init_profiles.py
**Dependencies:** 2
**Description:** Write unit tests for init_profiles()

### Task 7: Update installer tests for new profile behavior
**Files:** tests/test_installer.py
**Dependencies:** 4
**Description:** Update installer tests for new profile behavior

### Task 8: Update README with new init/discover commands
**Files:** README.md
**Dependencies:** 3
**Description:** Update README with new init/discover commands
