<?php

namespace Cauri\Services\Platforms;

/** Quota en mémoire (tests). */
final class MemoryQuotaStore extends QuotaStore
{
    private array $used = [];

    public function __construct()
    {
        parent::__construct(null);
    }

    public function used(string $api, string $day): int
    {
        return $this->used["$api|$day"] ?? 0;
    }

    public function add(string $api, string $day, int $units): void
    {
        $this->used["$api|$day"] = $this->used($api, $day) + $units;
    }
}
