<?php

namespace Cauri\Controllers\Admin;

use Cauri\Core\Request;
use Cauri\Core\Response;
use Cauri\Services\Audit;

final class AdminController extends BaseAdminController
{
    public function dashboard(Request $request): Response
    {
        $this->requireUser($request);
        return $this->admin('dashboard', [
            'pending'     => $this->db->all(
                "SELECT c.code, ws.week_start, COUNT(*) AS n FROM weekly_scores ws JOIN countries c ON c.id = ws.country_id
                 WHERE ws.review_status = 'pending' AND ws.score > 0 GROUP BY c.code, ws.week_start ORDER BY ws.week_start DESC"
            ),
            'drafts'      => $this->db->all(
                "SELECT c.code, r.period_type, r.period_key, COUNT(*) AS runs, MIN(r.id) AS first_id
                 FROM chart_runs r JOIN countries c ON c.id = r.country_id WHERE r.status = 'draft'
                 GROUP BY c.code, r.period_type, r.period_key ORDER BY MAX(r.period_end) DESC, c.code LIMIT 20"
            ),
            'submissions' => (int) $this->db->value("SELECT COUNT(*) FROM submissions WHERE status = 'pending'"),
            'messages'    => (int) $this->db->value("SELECT COUNT(*) FROM contact_messages WHERE status = 'new'"),
            'lastSnapshot'=> $this->db->value('SELECT MAX(captured_on) FROM snapshots'),
            'quota'       => $this->db->one("SELECT units_used FROM api_quota WHERE api = 'youtube' ORDER BY day DESC LIMIT 1"),
        ]);
    }

    public function audit(Request $request): Response
    {
        $this->requireUser($request, 'admin');
        $page = max(1, (int) $request->str('page', '1'));
        $rows = $this->db->all(
            'SELECT l.*, u.name AS user_name FROM audit_log l LEFT JOIN users u ON u.id = l.user_id ORDER BY l.id DESC LIMIT 100 OFFSET ' . (($page - 1) * 100)
        );
        return $this->admin('audit', ['rows' => $rows, 'page' => $page]);
    }

    public function messages(Request $request): Response
    {
        $this->requireUser($request);
        return $this->admin('messages', ['rows' => $this->db->all('SELECT * FROM contact_messages ORDER BY status = \'new\' DESC, id DESC LIMIT 200')]);
    }

    public function messageStatus(Request $request): Response
    {
        $this->requireUser($request);
        $status = $request->str('status');
        if (in_array($status, ['new', 'answered', 'closed'], true)) {
            $id = (int) $request->param('id');
            $this->db->update('contact_messages', ['status' => $status], 'id = :id', ['id' => $id]);
            Audit::log($this->uid(), 'message.status', 'contact_message', $id, null, ['status' => $status], $request->ip());
        }
        return $this->back(path('admin/messages'));
    }
}
