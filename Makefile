all: update

update:
	cp ../web/index.html .
	rsync --delete -av --exclude "cache" --exclude "config" --exclude "template" ../resources .
