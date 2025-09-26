import datetime as dt

import pytest

from quanticity_capital.core import models


def make_option_contract(**overrides):
    base = dict(
        symbol="SPY240621C00450000",
        option_type="call",
        strike=450.0,
        expiry=dt.date(2024, 6, 21),
        bid=1.5,
        ask=1.6,
        last=1.55,
        volume=100,
        open_interest=200,
        implied_volatility=0.25,
        greeks=models.OptionGreeks(delta=0.45, gamma=0.01, theta=-0.02, vega=0.12),
    )
    base.update(overrides)
    return models.OptionContract(**base)


def test_option_contract_mid_and_validation():
    contract = make_option_contract(bid=1.2, ask=1.8)
    assert contract.mid == pytest.approx(1.5)

    with pytest.raises(ValueError):
        make_option_contract(bid=2.0, ask=1.0)

    with pytest.raises(ValueError):
        make_option_contract(last=-0.5)


def test_options_chain_requires_contracts():
    contract = make_option_contract()
    chain = models.OptionsChain(
        symbol="SPY",
        as_of=dt.datetime(2024, 5, 1, 15, tzinfo=dt.timezone.utc),
        expiry=contract.expiry,
        underlying_price=453.21,
        contracts=[contract],
    )
    assert chain.by_type("call") == [contract]
    assert chain.by_type("put") == []

    with pytest.raises(ValueError):
        models.OptionsChain(
            symbol="SPY",
            as_of=dt.datetime.now(dt.timezone.utc),
            expiry=contract.expiry,
            underlying_price=453.21,
            contracts=[],
        )


def test_signal_sizing_rejects_zero_units():
    with pytest.raises(ValueError):
        models.SignalSizing(units=0.0)


@pytest.mark.parametrize(
    "order_type, limit_price, stop_price, expected_error",
    [
        ("limit", None, None, "limit orders require limit_price"),
        ("stop", None, None, "stop orders require stop_price"),
        ("stop_limit", None, 1.0, "limit orders require limit_price"),
    ],
)
def test_order_leg_validation(order_type, limit_price, stop_price, expected_error):
    with pytest.raises(ValueError) as exc:
        models.OrderLeg(
            symbol="SPY",
            quantity=1,
            order_type=order_type,
            limit_price=limit_price,
            stop_price=stop_price,
        )
    assert expected_error in str(exc.value)

    with pytest.raises(ValueError, match="quantity cannot be zero"):
        models.OrderLeg(symbol="SPY", quantity=0, order_type="market")


def test_order_request_requires_legs():
    leg = models.OrderLeg(symbol="SPY", quantity=1, order_type="market")
    request = models.OrderRequest(
        order_id="order-1",
        signal_id="signal-1",
        submitted_at=dt.datetime.now(dt.timezone.utc),
        legs=[leg],
    )
    assert request.legs == [leg]

    with pytest.raises(ValueError):
        models.OrderRequest(
            order_id="order-2",
            signal_id="signal-1",
            submitted_at=dt.datetime.now(dt.timezone.utc),
            legs=[],
        )


def test_social_post_content_validation():
    post = models.SocialPostDraft(
        post_id="post-1",
        platform="discord",
        tier="public",
        content=" Important update ",
        created_at=dt.datetime.now(dt.timezone.utc),
    )
    assert post.content == " Important update "

    with pytest.raises(ValueError):
        models.SocialPostDraft(
            post_id="post-2",
            platform="twitter",
            tier="public",
            content="   ",
            created_at=dt.datetime.now(dt.timezone.utc),
        )
