# Builds the portable core for the PC: a shared library for the Python
# simulator and the C unit tests.
CORE   := ../core
SRC    := $(wildcard $(CORE)/*.c)
HDR    := $(wildcard $(CORE)/*.h)
CFLAGS := -std=c99 -Wall -Wextra -Werror -O2 -I$(CORE)
EXT    := $(if $(filter Darwin,$(shell uname)),dylib,so)

all: build/libecu.$(EXT) build/libboot.$(EXT)

build/libecu.$(EXT): $(SRC) $(HDR) | build
	$(CC) $(CFLAGS) -shared -fPIC -o $@ $(SRC) -lm

build/test_core: test_core.c $(SRC) $(HDR) | build
	$(CC) $(CFLAGS) -o $@ test_core.c $(SRC) -lm

BOOT   := ../boot
BSRC   := $(BOOT)/boot.c $(CORE)/service.c $(CORE)/nvm.c $(CORE)/isotp.c $(CORE)/link.c
BHDR   := $(wildcard $(BOOT)/*.h) $(HDR)

build/libboot.$(EXT): $(BSRC) $(BHDR) | build
	$(CC) $(CFLAGS) -I$(BOOT) -shared -fPIC -o $@ $(BSRC)

build/test_boot: test_boot.c $(BSRC) $(BHDR) | build
	$(CC) $(CFLAGS) -I$(BOOT) -o $@ test_boot.c $(BSRC)

test: build/test_core build/test_boot
	./build/test_core
	./build/test_boot

build:
	mkdir -p build

.PHONY: all test
