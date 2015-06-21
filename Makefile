SRC = templates
DST = templates
SOURCES = $(wildcard $(SRC)/*.jade)
TARGETS = $(SOURCES:$(SRC)%.jade=$(DST)%.html.ep)

.SUFFIXES: .jade .html.ep .styl .css

all: $(TARGETS) public/default.css

.styl.css:
	stylus -u nib $<

.jade.html.ep:
	jade -P -o $(DST) $<
	mv -f $(@:%.html.ep=%.html) $@

clean :
	rm  $(wildcard $(DST)/*.html.ep)

cpan:
	cpanm -L local Config::Column Digest::SHA File::Spec File::MMagic git://github.com/jamadam/mojo-legacy.git
