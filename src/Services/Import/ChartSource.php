<?php

namespace Cauri\Services\Import;

/**
 * Une source de classement par pays (Apple Music, Audiomack, Boomplay...).
 * fetch() retourne null si le pays n'est pas couvert par la source, sinon :
 * ['observed_on' => 'Y-m-d', 'rows' => [['position', 'title', 'artist', 'external_id', 'url', 'image', 'release_date'], ...]]
 */
interface ChartSource
{
    public function key(): string;

    public function isAvailable(): bool;

    public function fetch(string $countryCode): ?array;
}
