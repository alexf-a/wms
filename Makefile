SVC?=wms
REGION?=us-east-1
POWER?=nano
SCALE?=1

.PHONY: docker-build deploy up down create push

docker-build:
	docker build -t $(SVC):latest .

create:
	aws lightsail create-container-service --region $(REGION) --service-name $(SVC) --power $(POWER) --scale $(SCALE)

push:
	aws lightsail push-container-image --region $(REGION) --service-name $(SVC) --label web --image $(SVC):latest

deploy:
	@if [ ! -f lightsail/containers.json ]; then echo "lightsail/containers.json missing (create from containers.example.json)"; exit 1; fi
	aws lightsail create-container-service-deployment \
		--region $(REGION) \
		--service-name $(SVC) \
		--containers file://lightsail/containers.json \
		--public-endpoint file://lightsail/public-endpoint.json

up: docker-build push deploy

down:
	aws lightsail delete-container-service --region $(REGION) --service-name $(SVC)
