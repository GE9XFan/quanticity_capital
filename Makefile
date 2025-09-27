
alerts-tail:
	redis-cli XREAD BLOCK 0 STREAMS stream:alerts $ > /tmp/alerts.log

alerts-last:
	redis-cli --scan --pattern state:alerts:last:* | xargs -n1 -I{} sh -c 'echo {}; redis-cli GET {}' | jq .

health:
	uv run python -m src.observability.cli heartbeat | jq .
