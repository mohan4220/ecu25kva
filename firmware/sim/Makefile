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

# ECU_MODEL=1: the control functions come from the code Embedded Coder
# generated out of model/*.slx (firmware/gen/), through core/model_glue.c.
# The same tests run against it: `make test-model`.
GEN    := ../gen
GENSRC := $(wildcard $(GEN)/*/*.c)
GENINC := $(addprefix -I,$(wildcard $(GEN)/*))
MFLAGS := $(CFLAGS) -DECU_MODEL $(GENINC)

build/libecu_model.$(EXT): $(SRC) $(HDR) $(GENSRC) | build
	$(CC) $(MFLAGS) -shared -fPIC -o $@ $(SRC) $(GENSRC) -lm

build/test_core_model: test_core.c $(SRC) $(HDR) $(GENSRC) | build
	$(CC) $(MFLAGS) -o $@ test_core.c $(SRC) $(GENSRC) -lm

test-model: build/test_core_model
	./build/test_core_model

build:
	mkdir -p build

.PHONY: all test test-model
