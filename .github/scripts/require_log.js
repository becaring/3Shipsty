// Closes bug reports that arrive without a log file or a description, and reopens them once fixed.
// Issue forms render each field as "### <label>"; dragged-in files become github.com/.../files/<id>/<name> links.
const LABEL = 'needs-log';
const MIN_DESCRIPTION = 40;

function sections(body) {
  const found = {};
  for (const part of (body || '').split(/^### /m).slice(1)) {
    const end = part.indexOf('\n');
    found[(end < 0 ? part : part.slice(0, end)).trim()] = end < 0 ? '' : part.slice(end + 1).trim();
  }
  return found;
}

// null for issues that are not bug reports; otherwise the list of missing pieces.
function problems(body) {
  const fields = sections(body);
  if (!('Log' in fields)) return null;
  const missing = [];
  if (!/github\.com\/(user-attachments|[\w.-]+\/[\w.-]+)\/files\/\d+\//.test(fields.Log)) {
    missing.push('your log file in the Log box (drag the file in; pasted text does not count)');
  }
  const what = (fields['What happened?'] || '').replace(/_No response_/g, '');
  if (what.replace(/\s/g, '').length < MIN_DESCRIPTION) {
    missing.push('a description under What happened?, saying what you did, what you expected and what you saw');
  }
  return missing;
}

async function run({ github, context }) {
  const issue = context.payload.issue;
  const missing = problems(issue.body);
  if (missing === null) return;
  const target = { owner: context.repo.owner, repo: context.repo.repo, issue_number: issue.number };
  const flagged = issue.labels.some((label) => label.name === LABEL);
  if (missing.length && issue.state === 'open') {
    await github.rest.issues.createComment({
      ...target,
      body: 'This report was closed automatically because it is missing:\n\n' +
        missing.map((item) => '- ' + item).join('\n') +
        '\n\nEdit the report to add them and it reopens.',
    });
    await github.rest.issues.addLabels({ ...target, labels: [LABEL] });
    await github.rest.issues.update({ ...target, state: 'closed', state_reason: 'not_planned' });
  } else if (!missing.length && flagged) {
    await github.rest.issues.removeLabel({ ...target, name: LABEL });
    if (issue.state === 'closed') await github.rest.issues.update({ ...target, state: 'open' });
  }
}

module.exports = run;

if (require.main === module) {
  const assert = require('assert');
  const log = '[game.log](https://github.com/user-attachments/files/123/game.log)';
  const good = '### What happened?\n\nThe game froze on character select right after I picked a fighter.\n\n### Log\n\n' + log;
  assert.deepStrictEqual(problems(good), []);
  assert.strictEqual(problems('### What happened?\n\nbroken\n\n### Log\n\n_No response_').length, 2);
  assert.strictEqual(problems(good.replace(log, 'pasted log text')).length, 1);
  assert.strictEqual(problems('### What would you like?\n\nMore stages'), null);
  console.log('require_log checks pass');
}
