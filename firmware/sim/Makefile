# Builds the portable core for the PC: a shared library for the Python
# simulator and the C unit tests.
CORE   := ../core
SRC    := $(wildcard $(CORE)/*.c)
HDR    := $(wildcard $(CORE)/*.h)
CFLAGS := -std=c99 -Wall -Wextra -Werror -O2 -I$(CORE)
EXT    := $(if $(filter Darwin,$(shell uname)),dylib,so)

all: build/libecu.$(EXT)

build/libecu.$(EXT): $(SRC) $(HDR) | build
	$(CC) $(CFLAGS) -shared -fPIC -o $@ $(SRC) -lm

build/test_core: test_core.c $(SRC) $(HDR) | build
	$(CC) $(CFLAGS) -o $@ test_core.c $(SRC) -lm

test: build/test_core
	./build/test_core

build:
	mkdir -p build

.PHONY: all test
