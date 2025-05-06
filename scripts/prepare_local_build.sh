rm -rf build
mkdir -p build

poetry build

cp dist/*.whl build/

cp docker/Dockerfile build/

mkdir -p build/resources
mkdir -p build/packages
mkdir -p build/submission/code/

cp dist/* build/packages/

cp -r tests/models_examples/bill/* build/submission/code/

cd build

docker build -t borisnieuwen/model_runner:latest -f Dockerfile .