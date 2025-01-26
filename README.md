# Hildebrand Glow (DCC) Bright Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge)](https://github.com/custom-components/hacs)
[![CodeFactor Grade](https://img.shields.io/codefactor/grade/github/HandyHat/ha-hildebrandglow-dcc?style=for-the-badge)](https://www.codefactor.io/repository/github/handyhat/ha-hildebrandglow-dcc)

Home Assistant integration for energy consumption data from UK SMETS (Smart) meters using the Hildebrand Glow API/Bright App.

The data retrieved from the API tends to be very behind - but I have made it backfill the past 24 hours, every half an hour.

## Installation

You will need an account at [Hildebrand](https://glowmarkt.com/register) and setup your property. I'm not sure how long it takes to get historic data.

## Installation through HACS

You can install this component through [HACS](https://hacs.xyz/) to easily receive updates. Once HACS is installed, click this link:

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=farkie&repository=ha-glowmarkt-bright)

<details>
  <summary>Manually add to HACS</summary>
  Visit the HACS Integrations pane and go to <i>Explore and download repositories</i>. 
  Search for <code>Hildebrand Glow (DCC)</code>, and then hit <i>Download</i>. 
  You'll then be able to install it through the <i>Integrations</i> pane.
</details>

## Thanks to:
Previous integration by HandyHat - https://github.com/HandyHat/ha-hildebrandglow-dcc
