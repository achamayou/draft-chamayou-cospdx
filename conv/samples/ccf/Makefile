all: manifest.spdx.packed.cbor manifest.spdx.analysis.txt

%.packed.cbor: %.json
	json2cbor.rb -p >$@ $<

%.analysis.txt: %.json analyze.rb Makefile
	json2cbor.rb $< | ruby analyze.rb >$@
